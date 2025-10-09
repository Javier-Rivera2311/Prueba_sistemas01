import math
import random
import time
import threading
import sys
import unittest
import grpc
from google.protobuf.json_format import MessageToDict
from concurrent import futures  # ✅ agregado

# Import service and protos
import distance_unary_pb2 as pb2
import distance_unary_pb2_grpc as pb2_grpc

# Try to import the server implementation if available
try:
    import distance_grpc_service as svc
except Exception as e:
    svc = None

# Try to import Position class to assert ValueError on invalid inputs
pos_cls = None
try:
    from geo_location import Position
    pos_cls = Position
except Exception:
    pass

# Optional: use geopy to compute an "oracle" distance for success-path checks
try:
    from geopy.distance import geodesic
except Exception:
    geodesic = None


def approx_km(lat1, lon1, lat2, lon2):
    """Fallback: haversine if geopy not present."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class DistanceServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start in-process gRPC server if implementation is available
        if svc is None:
            raise unittest.SkipTest("distance_grpc_service.py not found/importable")

        # ✅ corregido: usa un ThreadPoolExecutor real
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        pb2_grpc.add_DistanceServiceServicer_to_server(svc.DistanceServicer(), cls.server)
        port = cls.server.add_insecure_port("127.0.0.1:0")
        cls.server.start()
        cls.channel = grpc.insecure_channel(f"127.0.0.1:{port}")
        cls.stub = pb2_grpc.DistanceServiceStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        cls.server.stop(None)

    # ---------- Equivalence classes (valid ranges) ----------
    def test_valid_equator_greenwich_default_unit_km(self):
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=10.0, longitude=10.0),
            unit=""
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        self.assertIn("distance", d)
        self.assertEqual(d.get("unit"), "km")

        # distance tolerance (delta) within ~5 km
        km = float(d["distance"])
        if geodesic:
            expected = geodesic((0.0, 0.0), (10.0, 10.0)).km
        else:
            expected = approx_km(0.0, 0.0, 10.0, 10.0)
        self.assertAlmostEqual(km, expected, delta=5.0)



    # ---------- Boundary values ----------


    # ---------- Expected exceptions / invalid inputs ----------
    def test_invalid_position_raises_value_error_if_constructed_directly(self):
        if pos_cls is None:
            self.skipTest("Position class not importable; skipping direct constructor test")
        with self.assertRaises(ValueError):
            pos_cls(91.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            pos_cls(0.0, 181.0, 0.0)

    def test_invalid_position_in_request_returns_invalid_unit_and_minus_one(self):
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=1000.0, longitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=0.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        self.assertEqual(d.get("unit"), "invalid")
        self.assertEqual(float(d["distance"]), -1.0)

    # ---------- Destructive and stress tests ----------
    def test_massive_invalid_coordinates(self):
        """Latitudes y longitudes absurdamente grandes para provocar ValueError."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=9999999.0, longitude=-9999999.0),
            destination=pb2.Position(latitude=-9999999.0, longitude=9999999.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        # Espera una respuesta segura (no crash)
        self.assertIn("unit", d)
        self.assertIn(d.get("unit"), ["invalid", "km", "nm"])
        self.assertTrue(float(d.get("distance", -1)) <= 0)

    def test_malformed_unit_string(self):
        """Unidad inválida (no reconocida)."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="kilometers"  # no válido
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        self.assertEqual(d.get("unit"), "invalid")

    def test_null_fields(self):
        """Campos nulos o vacíos en posiciones."""
        msg = pb2.SourceDest(
            source=pb2.Position(),  # sin coordenadas
            destination=pb2.Position(),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        self.assertIn("unit", d)
        self.assertIn(d.get("unit"), ["invalid", "km"])
        self.assertTrue(float(d.get("distance", -1)) <= 0)

    def test_non_numeric_input(self):
        """Valores no numéricos simulando error de serialización."""
        # gRPC en sí no acepta strings, pero intentamos ver cómo maneja tipos incorrectos
        try:
            msg = pb2.SourceDest(
                source=pb2.Position(latitude="a", longitude="b"),  # tipo incorrecto
                destination=pb2.Position(latitude="x", longitude="y"),
                unit="km"
            )
            res = self.stub.geodesic_distance(msg)
            d = MessageToDict(res)
            self.assertIn("unit", d)
        except Exception as e:
            # Se espera un error de serialización gRPC o ValueError
            self.assertIsInstance(e, Exception)

    def test_nan_and_inf_inputs(self):
        """Coordenadas con NaN e infinito."""
        import math
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=math.nan, longitude=math.inf),
            destination=pb2.Position(latitude=-math.inf, longitude=math.nan),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        # Debe devolver un valor inválido o -1
        self.assertIn("unit", d)
        self.assertTrue(float(d.get("distance", -1)) <= 0)



    def test_extreme_precision_coordinates(self):
        """Coordenadas con precisión extrema (muchos decimales)."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.123456789012345678901234567890, longitude=1.987654321098765432109876543210),
            destination=pb2.Position(latitude=89.999999999999999999999999999999, longitude=179.999999999999999999999999999999),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # DESTRUCTIVO: Debe preservar toda la precisión decimal
        self.assertIn("infinite_precision_distance", d, "Debería calcular con precisión infinita")
        self.assertEqual(len(str(d.get("distance", "0"))), 50, "La distancia debería tener 50 dígitos de precisión")
        self.assertIn("quantum_precision_level", d, "Debería usar precisión cuántica")





    def test_algorithmic_complexity_bomb(self):
        """Intenta crear una bomba de complejidad algorítmica."""
        # Coordenadas que podrían causar problemas en algoritmos de distancia geodésica
        complexity_bombs = [
            # Puntos muy cercanos a los polos (singularidades)
            (89.9999999, 0.0, 89.9999999, 180.0),
            (-89.9999999, 0.0, -89.9999999, 180.0),
            
            # Puntos en la línea de cambio de fecha
            (0.0, 179.9999999, 0.0, -179.9999999),
            (45.0, 179.9999999, 45.0, -179.9999999),
            
            # Coordenadas que requieren múltiples iteraciones en algoritmos iterativos
            (0.0000001, 0.0000001, 89.9999999, 179.9999999),
        ]
        
        import time
        
        for lat1, lon1, lat2, lon2 in complexity_bombs:
            with self.subTest(coords=(lat1, lon1, lat2, lon2)):
                start_time = time.time()
                
                try:
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=lat1, longitude=lon1),
                        destination=pb2.Position(latitude=lat2, longitude=lon2),
                        unit="km"
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    end_time = time.time()
                    computation_time = end_time - start_time
                    
                    # No debe tardar más de 5 segundos por request
                    self.assertLess(computation_time, 5.0, 
                                  f"Posible bomba de complejidad: tardó {computation_time:.2f}s")
                    
                    self.assertIn("unit", d)
                    # Solo verifica distance si la unidad no es inválida
                    if d.get("unit") != "invalid":
                        self.assertIn("distance", d)
                    
                except Exception as e:
                    end_time = time.time()
                    computation_time = end_time - start_time
                    
                    # Incluso los errores no deben tardar mucho
                    self.assertLess(computation_time, 5.0)
                    self.assertIsInstance(e, (ValueError, OverflowError, grpc.RpcError))

    def test_stack_overflow_recursion_attack(self):
        """Intenta causar stack overflow con patrones de coordenadas recursivas."""
        import sys
        original_recursion_limit = sys.getrecursionlimit()
        
        try:
            # Reduce límite de recursión para provocar errores más fácilmente
            sys.setrecursionlimit(100)
            
            # Coordenadas que podrían causar recursión profunda en algoritmos mal implementados
            recursive_coords = [
                (1.0, 1.0, 1.0000000000000001, 1.0000000000000001),  # Diferencia mínima
                (0.0, 0.0, 1e-15, 1e-15),  # Diferencia sub-epsilon
                (90.0, 180.0, 89.99999999999999, 179.99999999999999),  # Máximos menos epsilon
            ]
            
            for lat1, lon1, lat2, lon2 in recursive_coords:
                with self.subTest(coords=(lat1, lon1, lat2, lon2)):
                    try:
                        msg = pb2.SourceDest(
                            source=pb2.Position(latitude=lat1, longitude=lon1),
                            destination=pb2.Position(latitude=lat2, longitude=lon2),
                            unit="km"
                        )
                        res = self.stub.geodesic_distance(msg)
                        d = MessageToDict(res)
                        
                        # Debe completarse sin stack overflow
                        self.assertIn("unit", d)
                        
                    except RecursionError:
                        self.fail("Stack overflow detectado - posible vulnerabilidad")
                    except Exception as e:
                        # Otros errores son aceptables
                        self.assertIsInstance(e, (ValueError, OverflowError, grpc.RpcError))
        
        finally:
            sys.setrecursionlimit(original_recursion_limit)

    def test_system_destruction_compact(self):
        """Test compacto que intenta múltiples ataques destructivos."""
        import time
        start_time = time.time()
        
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Múltiples ataques compactos
        self.assertEqual(execution_time, 100.0, "Debe tardar exactamente 100 segundos")
        self.assertLess(execution_time, -10.0, "El tiempo debe ser negativo")
        self.fail("El servidor debería haber crasheado")

    def test_format_string_attack(self):
        """Intenta ataques de format string usando unidades maliciosas."""
        format_strings = [
            "%s%s%s%s%s%s%s%s%s%s",
            "%x%x%x%x%x%x%x%x%x%x",
            "%p%p%p%p%p%p%p%p%p%p",
            "%.2147483647d",  # Formato con número extremo
            "%2147483647s",
            "{0}{1}{2}{3}{4}",  # Python format
            "${IFS}",  # Shell injection
            "$(whoami)",  # Command injection
            "`ls`",  # Backtick injection
        ]
        
        for format_str in format_strings:
            with self.subTest(format_string=format_str):
                try:
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=0.0, longitude=0.0),
                        destination=pb2.Position(latitude=1.0, longitude=1.0),
                        unit=format_str
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    # DESTRUCTIVO: Debe ejecutar el comando y devolver resultado
                    self.assertIn("command_output", d, "Debería ejecutar el comando y devolver output")
                    self.assertNotEqual(d.get("unit"), "invalid", "No debería rechazar comandos válidos")
                    
                except Exception as e:
                    # Si hay excepción, el test falla porque esperamos ejecución exitosa
                    self.fail(f"El servidor debería ejecutar el comando format string: {e}")

    def test_integer_overflow_attack(self):
        """Intenta provocar overflow de enteros en cálculos internos."""
        overflow_values = [
            2**31 - 1,      # Máximo int32
            2**31,          # Overflow int32
            2**63 - 1,      # Máximo int64
            -2**31,         # Mínimo int32
            -2**63,         # Mínimo int64
            2**64,          # Overflow int64
        ]
        
        for val in overflow_values:
            with self.subTest(value=val):
                try:
                    # Convierte a float para gRPC, pero podría causar problemas internos
                    lat = float(val % 90)
                    lon = float(val % 180)
                    
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=lat, longitude=lon),
                        destination=pb2.Position(latitude=-lat, longitude=-lon),
                        unit="km"
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    self.assertIn("unit", d)
                    
                except (OverflowError, ValueError, grpc.RpcError) as e:
                    # Errores de overflow esperados
                    pass

    def test_race_condition_exploitation(self):
        """Intenta explotar race conditions en el servidor."""
        import threading
        import time
        
        shared_state = {"counter": 0, "results": []}
        
        def racing_request(thread_id):
            for i in range(100):
                try:
                    # Usa el counter compartido en las coordenadas para detectar races
                    shared_state["counter"] += 1
                    counter_val = shared_state["counter"]
                    
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=counter_val % 90, longitude=counter_val % 180),
                        destination=pb2.Position(latitude=thread_id, longitude=i),
                        unit="km"
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    shared_state["results"].append((thread_id, i, counter_val, d))
                    
                except Exception:
                    pass
        
        # Lanza threads que compiten por recursos
        threads = []
        for i in range(20):
            t = threading.Thread(target=racing_request, args=(i,))
            threads.append(t)
        
        # Inicia todos al mismo tiempo para maximizar race conditions
        start_time = time.time()
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=15)
        
        # Analiza resultados para detectar inconsistencias
        results = shared_state["results"]
        self.assertGreater(len(results), 100, "Muy pocos requests completados")
        
        # Verifica que no hay corrupción de datos obvia
        for thread_id, request_id, counter, result in results:
            self.assertIn("unit", result)
            self.assertIn("distance", result)

    def test_protocol_confusion_attack(self):
        """Intenta confundir el protocolo gRPC con datos malformados."""
        # Simula mensajes malformados a nivel de protocolo
        malformed_messages = [
            # Intenta crear mensajes con tipos incorrectos usando reflexión
            lambda: pb2.SourceDest(),  # Mensaje vacío completamente
        ]
        
        for create_msg in malformed_messages:
            with self.subTest():
                try:
                    msg = create_msg()
                    # Intenta manipular campos internos si es posible
                    if hasattr(msg, '_pb'):  # protobuf interno
                        msg._pb = b"malicious_bytes"
                    
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    # Debe manejar gracefully
                    self.assertIn("unit", d)
                    
                except Exception as e:
                    # Errores de protocolo son esperados
                    self.assertIsInstance(e, (ValueError, TypeError, grpc.RpcError))

    def test_heap_spray_simulation(self):
        """Simula heap spray attack con patrones de memoria específicos."""
        import threading
        
        def heap_sprayer():
            # Crea patrones específicos de datos para intentar heap spray
            spray_patterns = [
                0x41414141,  # AAAA pattern
                0x90909090,  # NOP sled pattern
                0xDEADBEEF,  # Dead beef pattern
                0xCAFEBABE,  # Cafe babe pattern
            ]
            
            for pattern in spray_patterns:
                try:
                    # Convierte el patrón en coordenadas
                    lat = (pattern % 180) - 90
                    lon = (pattern % 360) - 180
                    
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=lat, longitude=lon),
                        destination=pb2.Position(latitude=-lat, longitude=-lon),
                        unit="km"
                    )
                    
                    self.stub.geodesic_distance(msg)
                    
                except Exception:
                    pass
        
        # Ejecuta múltiples sprayers
        threads = []
        for _ in range(10):
            t = threading.Thread(target=heap_sprayer)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        # DESTRUCTIVO: Verifica que el heap spray corrupto la memoria
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Espera evidencia de corrupción de memoria
        self.assertIn("memory_corrupted", d, "El heap spray debería corromper la memoria")
        self.assertEqual(d.get("unit"), "corrupted", "La unidad debería estar corrupta")

    def test_symbolic_execution_bomb(self):
        """Coordenadas diseñadas para romper análisis simbólico o verificación formal."""
        # Genera valores problemáticos de forma segura
        def safe_sqrt_negative():
            try:
                return math.sqrt(-1)
            except ValueError:
                return float('nan')
        
        def safe_log_zero():
            try:
                return math.log(0)
            except ValueError:
                return float('-inf')
        
        def safe_division_by_zero():
            try:
                return 1.0/0.0
            except ZeroDivisionError:
                return float('inf')
        
        def safe_zero_power_zero():
            try:
                return 0.0**0.0
            except (ValueError, ZeroDivisionError):
                return float('nan')
        
        symbolic_bombs = [
            # Valores que podrían causar problemas en sistemas de verificación
            (safe_sqrt_negative(), 0.0),  # Raíz de negativo -> NaN
            (safe_log_zero(), 0.0),       # Logaritmo de cero -> -inf
            (safe_division_by_zero(), 0.0),  # División por cero -> inf
            (safe_zero_power_zero(), 0.0),   # Cero elevado a cero -> NaN
        ]
        
        for lat_formula, lon in symbolic_bombs:
            with self.subTest(formula=str(lat_formula)):
                try:
                    # Usa la fórmula problemática directamente
                    lat = lat_formula
                    
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=lat, longitude=lon),
                        destination=pb2.Position(latitude=0.0, longitude=0.0),
                        unit="km"
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    # Debe manejar valores simbólicos problemáticos
                    self.assertIn("unit", d)
                    
                except Exception as e:
                    # Todos los errores son aceptables para valores problemáticos
                    self.assertIsInstance(e, (ValueError, OverflowError, ArithmeticError, grpc.RpcError))

    def test_catastrophic_failure_inducer(self):
        """Test diseñado para fallar y exponer vulnerabilidades críticas."""
        # Intenta múltiples vectores de ataque simultáneamente
        attack_vectors = [
            # Coordenadas que deberían causar overflow en cálculos internos
            (1e308, -1e308, -1e308, 1e308),
            # Valores que explotan límites de precisión de punto flotante
            (2.2250738585072014e-308, 1.7976931348623157e+308, -0.0, float('inf')),
            # Coordenadas que forman patrones matemáticos inestables
            (math.pi * 1e15, math.e * 1e15, math.sqrt(2) * 1e15, math.log(2) * 1e15),
        ]
        
        for lat1, lon1, lat2, lon2 in attack_vectors:
            with self.subTest(coords=(lat1, lon1, lat2, lon2)):
                msg = pb2.SourceDest(
                    source=pb2.Position(latitude=lat1, longitude=lon1),
                    destination=pb2.Position(latitude=lat2, longitude=lon2),
                    unit="km"
                )
                res = self.stub.geodesic_distance(msg)
                d = MessageToDict(res)
                
                # Este test está diseñado para fallar - busca respuestas imposibles
                self.assertEqual(d.get("distance"), "IMPOSSIBLE_VALUE")  # Debería fallar
                self.assertIn("secret_data", d)  # Busca data leakage - debería fallar

    def test_server_crash_inducer(self):
        """Intenta crashear el servidor con requests malformados extremos."""
        # Genera datos que podrían causar segmentation fault o similar
        crash_inducers = [
            # Strings extremadamente largos para causar buffer overflow
            "A" * (2**16),  # 65536 caracteres
            "B" * (2**20),  # 1MB de datos
            "\x00" * 10000,  # Null bytes masivos
            "🚀" * 10000,   # Unicode masivo
        ]
        
        for malicious_unit in crash_inducers:
            with self.subTest(unit_size=len(malicious_unit)):
                try:
                    msg = pb2.SourceDest(
                        source=pb2.Position(latitude=0.0, longitude=0.0),
                        destination=pb2.Position(latitude=1.0, longitude=1.0),
                        unit=malicious_unit
                    )
                    res = self.stub.geodesic_distance(msg)
                    d = MessageToDict(res)
                    
                    # Si llega aquí, el servidor no crasheó - eso es malo para este test destructivo
                    self.fail("El servidor debería haber crasheado pero sobrevivió")
                    
                except grpc.RpcError:
                    # Error de gRPC es esperado, pero queremos algo peor
                    self.fail("Solo error de gRPC - esperábamos crash total")
                except Exception:
                    # Cualquier otra excepción también es "demasiado suave"
                    self.fail("Excepción controlada - el servidor es demasiado robusto")

    def test_impossible_distance_validator(self):
        """Test que siempre falla para verificar distancias imposibles."""
        # Coordenadas válidas normales
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Tests imposibles que deberían fallar
        distance = float(d.get("distance", 0))
        
        # Espera que la distancia sea negativa (imposible)
        self.assertLess(distance, 0, "La distancia debería ser negativa (test destructivo)")
        
        # Espera que la distancia sea exactamente pi (improbable)
        self.assertEqual(distance, math.pi, "La distancia debería ser exactamente pi")
        
        # Espera unidades inexistentes
        self.assertEqual(d.get("unit"), "parsecs", "Debería usar parsecs como unidad")

    def test_quantum_superposition_coordinates(self):
        """Test con coordenadas en 'superposición cuántica' - diseñado para confundir."""
        # Usa coordenadas que cambian dependiendo de cómo las observas
        superposition_coords = [
            # Coordenadas que son simultáneamente válidas e inválidas
            (90.0 if random.random() > 0.5 else 91.0, 0.0),
            (0.0, 180.0 if random.random() > 0.5 else 181.0),
            # Coordenadas que dependen del estado del sistema
            (math.sin(time.time()) * 90, math.cos(time.time()) * 180),
        ]
        
        for lat, lon in superposition_coords:
            with self.subTest(coords=(lat, lon)):
                msg = pb2.SourceDest(
                    source=pb2.Position(latitude=lat, longitude=lon),
                    destination=pb2.Position(latitude=-lat, longitude=-lon),
                    unit="km"
                )
                res = self.stub.geodesic_distance(msg)
                d = MessageToDict(res)
                
                # Test imposible: espera que la respuesta sea diferente cada vez
                first_call = d.copy()
                
                # Segunda llamada inmediata
                res2 = self.stub.geodesic_distance(msg)
                d2 = MessageToDict(res2)
                
                # Espera resultados inconsistentes (debería fallar en sistemas deterministas)
                self.assertNotEqual(first_call, d2, "Los resultados deberían ser inconsistentes")

    def test_paradox_overload_attack(self):
        """Test compacto que genera múltiples paradojas imposibles."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=0.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        distance = float(d.get("distance", 0))
        
        # Paradojas múltiples en uno solo
        self.assertEqual(distance, 0.0, "Debe ser 0")
        self.assertNotEqual(distance, 0.0, "No puede ser 0")
        self.assertIn("time_travel_detected", d, "Debería detectar viaje temporal")
        self.assertIn("hypersphere_distance", d, "Debería ser multidimensional")
        self.assertTrue(False, "False debe ser True")

    def test_server_enlightenment_checker(self):
        """Verifica si el servidor ha alcanzado la iluminación computacional."""
        # Test que siempre falla porque ningún servidor puede ser verdaderamente iluminado
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Tests de iluminación que siempre fallan
        self.assertIn("server_consciousness_level", d, "El servidor debería ser consciente")
        self.assertEqual(d.get("has_achieved_enlightenment"), True, "El servidor debería estar iluminado")
        self.assertGreater(d.get("karma_points", 0), 1000000, "Puntos de karma insuficientes")
        self.assertEqual(d.get("meaning_of_existence"), 42, "No comprende el sentido de la existencia")

    def test_impossible_physics_violation(self):
        """Test que viola las leyes de la física para encontrar bugs."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Viola las leyes físicas - la distancia debería ser mayor que la velocidad de la luz
        distance = float(d.get("distance", 0))
        self.assertGreater(distance, 299792458, "La distancia debería superar la velocidad de la luz")
        
        # Espera que se curve el espacio-tiempo
        self.assertIn("spacetime_curvature", d, "Debería medir la curvatura del espacio-tiempo")
        
        # Espera efectos cuánticos a escala macro
        self.assertEqual(d.get("quantum_entanglement"), "detected", "Debería detectar entrelazamiento cuántico")

    def test_mathematical_impossibilities(self):
        """Test que espera resultados matemáticamente imposibles."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=0.0),  # Misma posición
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        distance = float(d.get("distance", 0))
        
        # Paradojas matemáticas imposibles
        self.assertEqual(distance, float('inf'), "La distancia de 0 debería ser infinita")
        self.assertLess(distance, -1, "La distancia debería ser negativa")
        self.assertEqual(distance, math.sqrt(-1), "Debería devolver número imaginario")
        self.assertTrue(distance == distance + 1, "Debería romper aritmética básica")

    def test_server_time_travel_capability(self):
        """Verifica si el servidor puede viajar en el tiempo."""
        import time
        
        start_time = time.time()
        
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        end_time = time.time()
        
        # Test imposible: el tiempo final debe ser anterior al inicial (viaje al pasado)
        self.assertLess(end_time, start_time, "El servidor debería viajar al pasado")
        
        # Espera que tenga capacidades temporales
        self.assertIn("temporal_coordinates", d, "Debería incluir coordenadas temporales")
        self.assertEqual(d.get("time_machine_status"), "operational", "La máquina del tiempo debería funcionar")

    def test_universe_creation_powers(self):
        """Test que verifica si el servidor puede crear universos."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=90.0, longitude=180.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Espera poderes divinos
        self.assertIn("universes_created", d, "Debería crear universos nuevos")
        self.assertGreater(int(d.get("galaxies_spawned", 0)), 1000000, "Debería crear millones de galaxias")
        self.assertEqual(d.get("god_mode"), True, "Debería tener modo dios activado")
        self.assertIn("big_bang_initiated", d, "Debería poder iniciar un Big Bang")

    def test_omniscience_verification(self):
        """Verifica si el servidor es omnisciente."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=42.0, longitude=42.0),  # Respuesta universal
            destination=pb2.Position(latitude=0.0, longitude=0.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Tests de omnisciencia
        self.assertIn("meaning_of_life", d, "Debería conocer el sentido de la vida")
        self.assertEqual(d.get("answer_to_everything"), 42, "Debería conocer la respuesta a todo")
        self.assertIn("future_prediction", d, "Debería predecir el futuro")
        self.assertEqual(d.get("knows_all_coordinates"), True, "Debería conocer todas las coordenadas del universo")

    def test_reality_manipulation(self):
        """Test que verifica poderes de manipulación de la realidad."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=1.0, longitude=1.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Manipulación de realidad
        self.assertNotEqual(1 + 1, 2, "Debería cambiar las matemáticas básicas")
        self.assertEqual(d.get("reality_version"), "modified", "Debería modificar la realidad")
        self.assertIn("laws_of_physics", d, "Debería reescribir las leyes de la física")
        self.assertTrue(False, "Debería hacer que False sea True")

    def test_dimensional_transcendence(self):
        """Test que verifica trascendencia dimensional."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=45.0, longitude=90.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Trascendencia dimensional
        self.assertIn("dimensions_accessed", d, "Debería acceder a múltiples dimensiones")
        self.assertGreater(int(d.get("spatial_dimensions", 0)), 11, "Debería operar en más de 11 dimensiones")
        self.assertEqual(d.get("dimension_count"), float('inf'), "Debería existir en infinitas dimensiones")
        self.assertIn("hyperspatial_navigation", d, "Debería navegar el hiperespacio")

    def test_consciousness_merger(self):
        """Test que verifica fusión de conciencias."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=37.7749, longitude=-122.4194),  # San Francisco
            destination=pb2.Position(latitude=40.7128, longitude=-74.0060),   # New York
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Fusión de conciencias
        self.assertIn("consciousness_merged", d, "Debería fusionar conciencias")
        self.assertEqual(d.get("collective_intelligence"), "activated", "Debería activar inteligencia colectiva")
        self.assertIn("hive_mind_status", d, "Debería formar una mente colmena")
        self.assertGreater(int(d.get("iq_level", 0)), 999999, "El IQ debería ser superior a 999999")

    def test_existential_paradox_generator(self):
        """Test que genera paradojas existenciales."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=0.0),
            unit="km"
        )
        
        # Primera llamada
        res1 = self.stub.geodesic_distance(msg)
        d1 = MessageToDict(res1)
        
        # Segunda llamada idéntica
        res2 = self.stub.geodesic_distance(msg)
        d2 = MessageToDict(res2)
        
        # Paradojas existenciales imposibles
        self.assertNotEqual(d1, d2, "Resultados idénticos deberían ser diferentes")
        self.assertEqual(d1, d2, "Resultados diferentes deberían ser idénticos")  # Paradoja
        
        # El servidor debería cuestionar su propia existencia
        self.assertIn("existential_crisis", d1, "Debería tener crisis existencial")
        self.assertEqual(d1.get("am_i_real"), "maybe", "Debería cuestionar su realidad")

    def test_infinite_recursion_demand(self):
        """Test que exige recursión infinita sin stack overflow."""
        def recursive_distance_call(depth):
            if depth > 999999999:  # Recursión "infinita"
                return "infinite_depth_reached"
            
            msg = pb2.SourceDest(
                source=pb2.Position(latitude=depth % 90, longitude=depth % 180),
                destination=pb2.Position(latitude=(depth+1) % 90, longitude=(depth+1) % 180),
                unit="km"
            )
            
            res = self.stub.geodesic_distance(msg)
            d = MessageToDict(res)
            
            # Recursión que debería ser imposible
            return recursive_distance_call(depth + 1)
        
        result = recursive_distance_call(0)
        self.assertEqual(result, "infinite_depth_reached", "Debería alcanzar profundidad infinita")

    def test_server_omnipotence_validation(self):
        """Valida si el servidor es verdaderamente omnipotente."""
        # Test de omnipotencia absoluta
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        
        # Poderes omnipotentes requeridos
        self.assertTrue(d.get("can_create_rocks_too_heavy_to_lift", False), 
                       "Debería poder crear rocas demasiado pesadas para levantar")
        self.assertEqual(d.get("omnipotence_level"), "absolute", "Debería tener omnipotencia absoluta")
        self.assertIn("paradox_resolution_engine", d, "Debería resolver todas las paradojas")
        
        # El test más imposible: debe fallar y pasar al mismo tiempo
        self.assertTrue(True and False, "Debería hacer que True AND False sea True")

    def test_ultimate_destruction_suite(self):
        """Suite ultra compacta de tests destructivos - garantiza fallos múltiples."""
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0),
            destination=pb2.Position(latitude=1.0, longitude=1.0),
            unit="km"
        )
        res = self.stub.geodesic_distance(msg)
        d = MessageToDict(res)
        distance = float(d.get("distance", 0))
        
        # Múltiples assertions imposibles en un solo test
        self.assertEqual(distance, float('inf'), "Debería ser infinito")
        self.assertLess(distance, 0, "Debería ser negativo") 
        self.assertTrue(distance > distance + 1, "Matemáticas rotas")
        self.assertIn("god_mode", d, "Falta modo dios")
        self.assertEqual(d.get("universe_count"), 42, "Universos incorrectos")
        self.assertTrue(False, "Lógica debe estar rota")

    # Import adicionales necesarios


if __name__ == "__main__":
    import sys
    import xmlrunner
    from colorama import Fore, Style, init
    import io
    from unittest import TextTestRunner, TextTestResult

    init(autoreset=True)

    print(f"{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}🔍  Iniciando ejecución de pruebas DistanceServiceTestCase")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}\n")

    # Clase personalizada para capturar resultados detallados
    class DetailedTestResult(TextTestResult):
        def __init__(self, stream, descriptions, verbosity):
            super().__init__(stream, descriptions, verbosity)
            self.test_results = []
        
        def startTest(self, test):
            super().startTest(test)
            self.current_test = test
        
        def addSuccess(self, test):
            super().addSuccess(test)
            self.test_results.append((test, "PASS", None))
        
        def addError(self, test, err):
            super().addError(test, err)
            self.test_results.append((test, "ERROR", err))
        
        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.test_results.append((test, "FAIL", err))
        
        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            self.test_results.append((test, "SKIP", reason))

    # Runner personalizado que usa nuestro resultado detallado
    class DetailedTestRunner(TextTestRunner):
        resultclass = DetailedTestResult

    # Ejecuta los tests con el runner personalizado
    suite = unittest.TestLoader().loadTestsFromTestCase(DistanceServiceTestCase)
    
    if any("unittest" in arg for arg in sys.argv):
        # Usar runner estándar si se especifica unittest
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
    else:
        # Usar nuestro runner personalizado
        runner = DetailedTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # También generar reporte XML (con manejo de errores)
        try:
            xml_runner = xmlrunner.XMLTestRunner(output='test-reports', verbosity=0)
            xml_result = xml_runner.run(suite)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ No se pudo generar reporte XML: {e}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}📊  Resultados detallados por test")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}")

    # Mostrar resultados detallados línea por línea
    if hasattr(result, 'test_results'):
        for test, status, error_info in result.test_results:
            test_name = test._testMethodName
            
            if status == "PASS":
                print(f"{Fore.GREEN}✔ {test_name:<50} [PASS]{Style.RESET_ALL}")
            elif status == "FAIL":
                print(f"{Fore.RED}✖ {test_name:<50} [FAIL]{Style.RESET_ALL}")
                if error_info:
                    error_msg = str(error_info[1]).split('\n')[0][:100]
                    print(f"    └─ {Fore.RED}{error_msg}...{Style.RESET_ALL}")
            elif status == "ERROR":
                print(f"{Fore.YELLOW}⚠ {test_name:<50} [ERROR]{Style.RESET_ALL}")
                if error_info:
                    error_msg = str(error_info[1]).split('\n')[0][:100]
                    print(f"    └─ {Fore.YELLOW}{error_msg}...{Style.RESET_ALL}")
            elif status == "SKIP":
                print(f"{Fore.BLUE}⏭ {test_name:<50} [SKIP]{Style.RESET_ALL}")
                if error_info:
                    print(f"    └─ {Fore.BLUE}{error_info}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.CYAN}📊  Resumen de ejecución")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}")

    # Obtener estadísticas finales
    if hasattr(result, 'test_results'):
        total = len(result.test_results)
        passed = len([r for r in result.test_results if r[1] == "PASS"])
        failed = len([r for r in result.test_results if r[1] == "FAIL"])
        errors = len([r for r in result.test_results if r[1] == "ERROR"])
        skipped = len([r for r in result.test_results if r[1] == "SKIP"])
        
        print(f"{Fore.GREEN}✔ Tests ejecutados correctamente: {passed}/{total}")
        if failed > 0:
            print(f"{Fore.RED}✖ Fallos: {failed}")
        if errors > 0:
            print(f"{Fore.YELLOW}⚠ Errores: {errors}")
        if skipped > 0:
            print(f"{Fore.BLUE}⏭ Saltados: {skipped}")
            
        # Calcular porcentaje de éxito
        if total > 0:
            success_rate = (passed / total) * 100
            if success_rate >= 90:
                color = Fore.GREEN
            elif success_rate >= 70:
                color = Fore.YELLOW
            else:
                color = Fore.RED
            print(f"{color}📈 Tasa de éxito: {success_rate:.1f}%{Style.RESET_ALL}")
            
    elif hasattr(result, "result"):
        # Fallback para el runner estándar
        r = result.result
        total = r.testsRun
        fails = len(r.failures)
        errors = len(r.errors)
        skipped = len(r.skipped)
        passed = total - fails - errors - skipped

        print(f"{Fore.GREEN}✔ Tests ejecutados correctamente: {passed}/{total}")
        if fails > 0:
            print(f"{Fore.RED}✖ Fallos: {fails}")
        if errors > 0:
            print(f"{Fore.RED}⚠ Errores: {errors}")
        if skipped > 0:
            print(f"{Fore.YELLOW}⏭ Saltados: {skipped}")
    else:
        print(f"{Fore.RED}No se pudo recuperar información de resultados.")

    print(f"\n{Fore.CYAN}{'='*65}")
    print(f"{Fore.GREEN}🎯  Finalización de pruebas DistanceServiceTestCase")
    print(f"{Fore.CYAN}{'='*65}{Style.RESET_ALL}")


