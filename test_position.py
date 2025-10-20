import unittest
import sys
import os

# Add the current directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from geo_location import Position


class TestPosition(unittest.TestCase):
    """
    Unit tests for Position class following equivalence classes and boundary value analysis.
    
    Tests cover:
    - Valid latitude ranges: [-90, 90]
    - Valid longitude ranges: [-180, 180]
    - Boundary values for both coordinates
    - Expected exceptions for out-of-range values
    """

    def setUp(self):
        """Set up test fixtures with common altitude value."""
        self.default_altitude = 0.0

    # ========== SUCCESS PATH TESTS ==========

    def test_valid_position_equator_greenwich(self):
       
        # EC2 (latitude = 0) and EC7 (longitude = 0)
        position = Position(0.0, 0.0, self.default_altitude)
        self.assertEqual(position._latitude, 0.0)
        self.assertEqual(position._longitude, 0.0)
        self.assertEqual(position._altitude, self.default_altitude)

    def test_valid_position_boundary_values(self):
        """
        TEST DE VALORES FRONTERA: Verifica límites exactos válidos del sistema
        
        PROPÓSITO: Valida que Position acepte exactamente los límites especificados
        CLASE DE EQUIVALENCIA: EC_Boundary_Valid - Valores en frontera válidos
        MÉTODO: Boundary Value Test - límites exactos deben ser aceptados
        
        LÍMITES DE REQUISITOS: -90 ≤ latitud ≤ 90, -180 ≤ longitud ≤ 180
        CASOS CRÍTICOS: Polos (±90°) y Antimeridiano (±180°)
        VALIDACIÓN: No debe lanzar excepciones para estos valores exactos
        """
        # Casos límite válidos
        Position(90.0, 180.0, self.default_altitude)   # Límites superiores
        Position(-90.0, -180.0, self.default_altitude) # Límites inferiores

    def test_valid_position_santiago_chile(self):
        """
        TEST FUNCIONAL: Valida posición real con coordenadas del mundo real  
        
        PROPÓSITO: Verifica Position con coordenadas geográficas reales (no casos teóricos)
        CLASE DE EQUIVALENCIA: EC1_Lat (latitud negativa) + EC6_Lon (longitud negativa)
        MÉTODO: Success Path Test - coordenadas reales deben ser procesadas correctamente
        
        DATOS REALES: Santiago, Chile (-33.4489°, -70.6693°) - Capital sudamericana
        VALIDACIÓN: Hemisferio Sur + Hemisferio Occidental (ambos valores negativos)
        VERIFICACIÓN: Valores asignados exactamente como se proporcionaron
        """
        # EC1 (negative latitude) and EC6 (negative longitude)
        santiago_lat, santiago_lon = -33.4489, -70.6693
        position = Position(santiago_lat, santiago_lon, self.default_altitude)
        self.assertEqual(position._latitude, santiago_lat)
        self.assertEqual(position._longitude, santiago_lon)

    # Otros casos válidos eliminados para presentación más concisa

    # ========== EXPECTED EXCEPTION TESTS ==========

    def test_latitude_too_high_boundary(self):

        # EC5: latitude > 90 (boundary violation)
        with self.assertRaises(ValueError) as context:
            Position(90.1, 0.0, self.default_altitude)
        self.assertIn("Latitude out of range", str(context.exception))

    def test_latitude_significantly_too_high(self):
        """
        TEST DE EXCEPCIÓN ESPERADA: Verifica rechazo de latitud muy alta ✅ PASA
        
        PROPÓSITO: Validar rechazo de valores extremadamente fuera de rango (no solo frontera)
        CLASE DE EQUIVALENCIA: EC5_Lat_Invalid (latitud >> 90) - Casos extremos inválidos  
        MÉTODO: Expected Exception Test - debe lanzar ValueError
        
        VALOR EXTREMO: 150° (muy fuera del rango geográfico válido)
        COMPORTAMIENTO ESPERADO: ValueError("Latitude out of range!")
        ESTADO: ✅ IMPLEMENTACIÓN CORRECTA - Límites superiores funcionan bien
        """
        # EC5: latitude >> 90
        with self.assertRaises(ValueError) as context:
            Position(150.0, 0.0, self.default_altitude)
        self.assertIn("Latitude out of range", str(context.exception))

    def test_latitude_too_low_boundary(self):

        with self.assertRaises(ValueError, msg="ERROR DEL SISTEMA: La implementación no valida latitud < -90° como debe según los requisitos"):
            Position(-90.1, 0.0, self.default_altitude)

    def test_latitude_significantly_too_low(self):

        # EC4: latitude << -90
        # ESTE TEST DEBE FALLAR porque el sistema no valida límites inferiores
        with self.assertRaises(ValueError, msg="ERROR DEL SISTEMA: Latitud -150° debe ser rechazada pero la implementación no la valida"):
            Position(-150.0, 0.0, self.default_altitude)

    def test_longitude_too_high_boundary(self):
        # EC10: longitude > 180 (boundary violation)
        with self.assertRaises(ValueError) as context:
            Position(0.0, 180.1, self.default_altitude)
        self.assertIn("Longitude out of range", str(context.exception))

    def test_longitude_too_low_boundary(self):
        # EC9: longitude < -180 (violación de límite)
        # ESTE TEST DEBE FALLAR porque la implementación no valida límite inferior
        with self.assertRaises(ValueError, msg="ERROR DEL SISTEMA: La implementación no valida longitud < -180° según requisitos"):
            Position(0.0, -180.1, self.default_altitude)

    def test_longitude_significantly_too_low(self):
        """Prueba que longitud significativamente baja lance ValueError."""
        # EC9: longitude << -180
        # ESTE TEST DEBE FALLAR porque el sistema no valida límites inferiores
        with self.assertRaises(ValueError, msg="ERROR DEL SISTEMA: Longitud -270° debe ser rechazada pero la implementación no la valida"):
            Position(0.0, -270.0, self.default_altitude)

    def test_both_coordinates_invalid_low(self):
        """Prueba que ambas coordenadas fuera de rango (bajas) lance ValueError."""
        # EC4 + EC9: ambas coordenadas < límites inferiores
        # ESTE TEST DEBE FALLAR porque el sistema no valida límites inferiores
        with self.assertRaises(ValueError, msg="ERROR DEL SISTEMA: Coordenadas (-95°, -185°) deben ser rechazadas pero la implementación no las valida"):
            Position(-95.0, -185.0, self.default_altitude)


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)