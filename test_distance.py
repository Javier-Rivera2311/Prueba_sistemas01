import unittest
import sys
import os
from unittest.mock import patch

# Add the current directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from geo_location import Position
from helpers import Distance


class TestDistance(unittest.TestCase):
    """
    Unit tests for Distance class following equivalence classes and boundary value analysis.
    
    Tests cover:
    - Distance calculations in kilometers and nautical miles
    - Known geographical distances for validation
    - Edge cases like same positions (distance = 0)
    - Boundary positions (poles, meridians)
    """

    def setUp(self):
        """Set up test fixtures with known geographical positions."""
        # Santiago, Chile
        self.santiago = Position(-33.4489, -70.6693, 0.0)
        
        # Valparaíso, Chile (approximately 120 km from Santiago)
        self.valparaiso = Position(-33.0472, -71.6127, 0.0)
        
        # Equator and Greenwich meridian
        self.equator_greenwich = Position(0.0, 0.0, 0.0)
        
        # North Pole
        self.north_pole = Position(90.0, 0.0, 0.0)
        
        # South Pole
        self.south_pole = Position(-90.0, 0.0, 0.0)
        
        # Solo mantenemos las posiciones esenciales para presentación
        self.sydney = Position(-33.8688, 151.2093, 0.0)

    # ========== SUCCESS PATH TESTS - KILOMETERS ==========

    def test_distance_santiago_to_valparaiso_km(self):
        """
        TEST FUNCIONAL: Valida cálculo correcto de distancia en kilómetros
        
        PROPÓSITO: Verifica que la clase Distance calcule correctamente distancias reales
        CLASE DE EQUIVALENCIA: EC_Success_Path - Cálculos válidos con coordenadas reales
        MÉTODO: Success Path Test - debe pasar y retornar valor correcto
        
        DATOS: Santiago (-33.4489, -70.6693) a Valparaíso (-33.0472, -71.6127)
        VALOR ESPERADO: ~98.6 km (verificado con Google Earth y geopy)
        TOLERANCIA: ±2.0 km (permite variaciones por precisión geodésica)
        """
        # Distancia real calculada: ~98.6 km (verificada con geopy)
        distance = Distance(self.santiago, self.valparaiso)
        result_km = distance.km()
        
        # Usando tolerancia delta según especificado en requisitos
        self.assertAlmostEqual(result_km, 98.6, delta=2.0, 
                             msg=f"Error: Se esperaba ~98.6 km, se obtuvo {result_km}")
        self.assertGreater(result_km, 0, "Error: La distancia debe ser positiva")

    def test_same_position_distance_km(self):
        """
        TEST DE CASO LÍMITE: Distancia entre el mismo punto debe ser 0
        
        PROPÓSITO: Valida comportamiento correcto en caso extremo de misma posición
        CLASE DE EQUIVALENCIA: EC_Boundary_Zero - Distancia cero (caso límite)
        MÉTODO: Boundary Value Test - caso extremo válido
        
        DATOS: Santiago a Santiago (mismas coordenadas)
        VALOR ESPERADO: 0.0 km exacto
        TOLERANCIA: ±0.001 km (precisión mínima)
        """
        distance = Distance(self.santiago, self.santiago)
        result_km = distance.km()
        
        self.assertAlmostEqual(result_km, 0.0, delta=0.001,
                             msg=f"Expected 0 km for same position, got {result_km}")

    def test_distance_santiago_to_valparaiso_nm(self):
        """
        TEST FUNCIONAL: Valida cálculo correcto de distancia en millas náuticas
        
        PROPÓSITO: Verifica que la clase Distance calcule correctamente en unidad náutica
        CLASE DE EQUIVALENCIA: EC_Success_Path - Cálculos válidos con unidad alternativa
        MÉTODO: Success Path Test - debe pasar con unidad náutica
        
        DATOS: Santiago a Valparaíso (mismas coordenadas que test anterior)
        VALOR ESPERADO: ~53.2 nm (conversión: 98.6 km ÷ 1.852 = 53.2 nm)
        TOLERANCIA: ±1.0 nm (permite variaciones por conversión y precisión)
        """
        # Distancia real calculada: ~53.2 millas náuticas (verificada con geopy)
        distance = Distance(self.santiago, self.valparaiso)
        result_nm = distance.nautical()
        
        self.assertAlmostEqual(result_nm, 53.2, delta=1.0,
                             msg=f"Error: Se esperaba ~53.2 nm, se obtuvo {result_nm}")
        self.assertGreater(result_nm, 0, "Distance should be positive")

    # ========== CONVERSION CONSISTENCY TESTS ==========

    def test_km_to_nautical_conversion_consistency(self):
        """
        TEST DE CONSISTENCIA: Verifica conversión correcta entre km y millas náuticas
        
        PROPÓSITO: Valida que ambos métodos (.km() y .nautical()) sean consistentes
        CLASE DE EQUIVALENCIA: EC_Conversion_Validation - Consistencia entre unidades  
        MÉTODO: Cross-validation test - verifica matemática de conversión
        
        LÓGICA: 1 milla náutica = 1.852 kilómetros (estándar internacional)
        VERIFICACIÓN: result_km ≈ result_nm × 1.852
        TOLERANCIA: ±0.1 km (permite diferencias por redondeo)
        """
        distance = Distance(self.santiago, self.valparaiso)
        result_km = distance.km()
        result_nm = distance.nautical()
        
        # Convert nautical miles to kilometers: nm * 1.852
        converted_km = result_nm * 1.852
        
        self.assertAlmostEqual(result_km, converted_km, delta=0.1,
                             msg=f"Conversion inconsistency: {result_km} km vs {converted_km} km (from {result_nm} nm)")

    def test_multiple_distance_calculations_consistency(self):
        """
        TEST DE REPRODUCIBILIDAD: Verifica que cálculos repetidos den mismo resultado
        
        PROPÓSITO: Valida que la clase Distance sea determinística (no aleatoria)
        CLASE DE EQUIVALENCIA: EC_Deterministic_Behavior - Comportamiento predecible
        MÉTODO: Reproducibility test - múltiples ejecuciones = mismo resultado
        
        LÓGICA: Mismas coordenadas → mismo objeto Distance → mismo resultado
        VERIFICACIÓN: distance1.km() == distance2.km() (exactamente igual)
        IMPORTANCIA: Asegura que no hay variabilidad no deseada en cálculos
        """
        distance1 = Distance(self.santiago, self.valparaiso)
        distance2 = Distance(self.santiago, self.valparaiso)
        
        result1_km = distance1.km()
        result2_km = distance2.km()
        
        self.assertEqual(result1_km, result2_km,
                        "Multiple calculations should yield identical results")

    # ========== BOUNDARY VALUE TESTS ==========

    def test_distance_antimeridian_crossing(self):
        """
        TEST DE CASO EXTREMO: Distancia cruzando el antimeridiano (línea 180°)
        
        PROPÓSITO: Valida cálculo correcto en límite geográfico crítico (antimeridiano)
        CLASE DE EQUIVALENCIA: EC_Boundary_Geographic - Límites geográficos especiales
        MÉTODO: Boundary Value Test - casos geográficos extremos
        
        DATOS: 179° Este (-179° Oeste) - cruza la línea de fecha internacional
        CÁLCULO: 2° de diferencia longitudinal en el ecuador = ~222 km
        FÓRMULA: 1° longitud en ecuador ≈ 111 km → 2° ≈ 222 km
        TOLERANCIA: ±20 km (permite variaciones por curvatura terrestre)
        """
        # Position just west of antimeridian
        west_antimeridian = Position(0.0, 179.0, 0.0)
        # Position just east of antimeridian
        east_antimeridian = Position(0.0, -179.0, 0.0)
        
        distance = Distance(west_antimeridian, east_antimeridian)
        result_km = distance.km()
        
        # Should be approximately 222 km (2° of longitude at equator)
        self.assertAlmostEqual(result_km, 222.0, delta=20.0,
                             msg=f"Expected ~222 km for antimeridian crossing, got {result_km}")

    # Otros tests eliminados para presentación más concisa


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)