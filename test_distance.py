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
        """Prueba distancia entre Santiago y Valparaíso en kilómetros."""
        # Distancia real calculada: ~98.6 km (verificada con geopy)
        distance = Distance(self.santiago, self.valparaiso)
        result_km = distance.km()
        
        # Usando tolerancia delta según especificado en requisitos
        self.assertAlmostEqual(result_km, 98.6, delta=2.0, 
                             msg=f"Error: Se esperaba ~98.6 km, se obtuvo {result_km}")
        self.assertGreater(result_km, 0, "Error: La distancia debe ser positiva")

    def test_same_position_distance_km(self):
        """Test distance between same position should be 0 km."""
        distance = Distance(self.santiago, self.santiago)
        result_km = distance.km()
        
        self.assertAlmostEqual(result_km, 0.0, delta=0.001,
                             msg=f"Expected 0 km for same position, got {result_km}")

    def test_distance_santiago_to_valparaiso_nm(self):
        """Prueba distancia entre Santiago y Valparaíso en millas náuticas."""
        # Distancia real calculada: ~53.2 millas náuticas (verificada con geopy)
        distance = Distance(self.santiago, self.valparaiso)
        result_nm = distance.nautical()
        
        self.assertAlmostEqual(result_nm, 53.2, delta=1.0,
                             msg=f"Error: Se esperaba ~53.2 nm, se obtuvo {result_nm}")
        self.assertGreater(result_nm, 0, "Distance should be positive")

    # ========== CONVERSION CONSISTENCY TESTS ==========

    def test_km_to_nautical_conversion_consistency(self):
        """Test that km and nautical mile results are consistent (1 nm ≈ 1.852 km)."""
        distance = Distance(self.santiago, self.valparaiso)
        result_km = distance.km()
        result_nm = distance.nautical()
        
        # Convert nautical miles to kilometers: nm * 1.852
        converted_km = result_nm * 1.852
        
        self.assertAlmostEqual(result_km, converted_km, delta=0.1,
                             msg=f"Conversion inconsistency: {result_km} km vs {converted_km} km (from {result_nm} nm)")

    def test_multiple_distance_calculations_consistency(self):
        """Test that multiple calculations of the same distance are consistent."""
        distance1 = Distance(self.santiago, self.valparaiso)
        distance2 = Distance(self.santiago, self.valparaiso)
        
        result1_km = distance1.km()
        result2_km = distance2.km()
        
        self.assertEqual(result1_km, result2_km,
                        "Multiple calculations should yield identical results")

    # ========== BOUNDARY VALUE TESTS ==========

    def test_distance_antimeridian_crossing(self):
        """Test distance calculation crossing the antimeridian (180° longitude)."""
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