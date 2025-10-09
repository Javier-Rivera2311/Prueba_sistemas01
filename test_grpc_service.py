import unittest
import grpc
import sys
import os
from concurrent import futures
import threading
import time

# Add the current directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import distance_unary_pb2_grpc as pb2_grpc
import distance_unary_pb2 as pb2
from distance_grpc_service import DistanceServicer


class TestDistanceGRPCService(unittest.TestCase):
    """
    Integration tests for the gRPC Distance Service following equivalence classes and boundary value analysis.
    
    Tests cover:
    - Valid requests with different units (km, nm, empty)
    - Invalid coordinate requests (should return distance = -1, unit = "invalid")
    - Success path and expected error scenarios
    - Full end-to-end gRPC communication
    """

    @classmethod
    def setUpClass(cls):
        """Set up gRPC server for testing."""
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        pb2_grpc.add_DistanceServiceServicer_to_server(DistanceServicer(), cls.server)
        
        # Use a test port to avoid conflicts
        cls.test_port = 50052
        cls.server.add_insecure_port(f'[::]:{cls.test_port}')
        cls.server.start()
        
        # Give server time to start
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        """Clean up gRPC server after testing."""
        cls.server.stop(grace=None)

    def setUp(self):
        """Set up gRPC client for each test."""
        self.channel = grpc.insecure_channel(f'localhost:{self.test_port}')
        self.stub = pb2_grpc.DistanceServiceStub(self.channel)

    def tearDown(self):
        """Clean up gRPC client after each test."""
        self.channel.close()

    # ========== SUCCESS PATH TESTS ==========

    def test_valid_distance_request_km(self):
        """Prueba solicitud válida de distancia con unidad km."""
        # Santiago a Valparaíso, Chile (~98.6 km real calculado)
        message = pb2.SourceDest(
            source=pb2.Position(latitude=-33.4489, longitude=-70.6693, altitude=0.0),
            destination=pb2.Position(latitude=-33.0472, longitude=-71.6127, altitude=0.0),
            unit="km"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertAlmostEqual(response.distance, 98.6, delta=2.0,
                             msg=f"Error: Se esperaba ~98.6 km, se obtuvo {response.distance}")
        self.assertEqual(response.method, "geodesic", "El método debe ser geodesic")
        self.assertEqual(response.unit, "km", "La unidad debe ser km")
        self.assertGreater(response.distance, 0, "La distancia debe ser positiva")

    # Test nm eliminado para presentación concisa

    def test_valid_distance_request_empty_unit_default_km(self):
        """Prueba solicitud válida con unidad vacía (debe usar km por defecto)."""
        # Tokio a Sydney (~7,823 km en realidad, pero el servicio tiene un bug)
        message = pb2.SourceDest(
            source=pb2.Position(latitude=35.6762, longitude=139.6503, altitude=0.0),
            destination=pb2.Position(latitude=-33.8688, longitude=151.2093, altitude=0.0),
            unit=""  # Unidad vacía debe usar km por defecto
        )
        
        response = self.stub.geodesic_distance(message)
        
        # ESTE TEST DEBE FALLAR porque hay un BUG en distance_grpc_service.py línea 32:
        # Usa .nautical() cuando debería usar .km() para unidad vacía
        self.assertAlmostEqual(response.distance, 7823.0, delta=100.0,
                             msg=f"ERROR DEL SISTEMA: El servicio usa .nautical() en lugar de .km() para unidad vacía. Esperaba ~7,823 km, obtuvo {response.distance}")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "km", "La unidad vacía debe retornar 'km' por defecto")
        self.assertGreater(response.distance, 0, "La distancia debe ser positiva")

    # Tests de casos válidos eliminados para presentación más concisa

    # ========== EXPECTED ERROR TESTS ==========

    def test_invalid_latitude_too_high_source(self):
        """Test invalid source latitude > 90 returns error response."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=95.0, longitude=0.0, altitude=0.0),  # Invalid latitude
            destination=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0),
            unit="km"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    def test_invalid_latitude_too_low_source(self):
        """Test invalid source latitude < -90 returns error response."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=-95.0, longitude=0.0, altitude=0.0),  # Invalid latitude
            destination=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0),
            unit="km"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    def test_invalid_longitude_too_high_destination(self):
        """Test invalid destination longitude > 180 returns error response."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=185.0, altitude=0.0),  # Invalid longitude
            unit="nm"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    def test_invalid_longitude_too_low_destination(self):
        """Test invalid destination longitude < -180 returns error response."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=0.0, longitude=0.0, altitude=0.0),
            destination=pb2.Position(latitude=0.0, longitude=-185.0, altitude=0.0),  # Invalid longitude
            unit="nm"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    def test_both_positions_invalid_coordinates(self):
        """Test both source and destination with invalid coordinates."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=100.0, longitude=200.0, altitude=0.0),     # Both invalid
            destination=pb2.Position(latitude=-100.0, longitude=-200.0, altitude=0.0), # Both invalid
            unit="km"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    def test_mixed_valid_invalid_coordinates(self):
        """Test valid source with invalid destination coordinates."""
        message = pb2.SourceDest(
            source=pb2.Position(latitude=40.7128, longitude=-74.0060, altitude=0.0),  # Valid (NYC)
            destination=pb2.Position(latitude=95.0, longitude=0.0, altitude=0.0),      # Invalid latitude
            unit="km"
        )
        
        response = self.stub.geodesic_distance(message)
        
        self.assertEqual(response.distance, -1.0, "Invalid coordinates should return distance = -1")
        self.assertEqual(response.method, "geodesic")
        self.assertEqual(response.unit, "invalid", "Invalid coordinates should return unit = 'invalid'")

    # ========== UNIT CONVERSION CONSISTENCY TESTS ==========

    def test_km_nm_conversion_consistency(self):
        """Test that km and nm results are consistent for the same positions."""
        source_pos = pb2.Position(latitude=51.5074, longitude=-0.1278, altitude=0.0)  # London
        dest_pos = pb2.Position(latitude=48.8566, longitude=2.3522, altitude=0.0)     # Paris
        
        # Test with km
        message_km = pb2.SourceDest(source=source_pos, destination=dest_pos, unit="km")
        response_km = self.stub.geodesic_distance(message_km)
        
        # Test with nm
        message_nm = pb2.SourceDest(source=source_pos, destination=dest_pos, unit="nm")
        response_nm = self.stub.geodesic_distance(message_nm)
        
        # Verify conversion consistency (1 nautical mile ≈ 1.852 km)
        expected_km_from_nm = response_nm.distance * 1.852
        self.assertAlmostEqual(response_km.distance, expected_km_from_nm, delta=0.5,
                             msg=f"Conversion inconsistency: {response_km.distance} km vs {expected_km_from_nm} km from {response_nm.distance} nm")

    def test_empty_unit_equals_km_unit(self):
        """Prueba que unidad vacía dé el mismo resultado que unidad km explícita."""
        source_pos = pb2.Position(latitude=35.6762, longitude=139.6503, altitude=0.0)  # Tokio
        dest_pos = pb2.Position(latitude=37.7749, longitude=-122.4194, altitude=0.0)   # San Francisco
        
        # Prueba con km explícito
        message_km = pb2.SourceDest(source=source_pos, destination=dest_pos, unit="km")
        response_km = self.stub.geodesic_distance(message_km)
        
        # Prueba con unidad vacía (debe usar km por defecto)
        message_empty = pb2.SourceDest(source=source_pos, destination=dest_pos, unit="")
        response_empty = self.stub.geodesic_distance(message_empty)
        
        # ESTE TEST DEBE FALLAR por el bug en distance_grpc_service.py línea 32
        self.assertAlmostEqual(response_km.distance, response_empty.distance, delta=0.001,
                             msg=f"ERROR DEL SISTEMA: Unidad vacía debería usar .km() pero usa .nautical(). KM={response_km.distance}, Vacía={response_empty.distance}")
        self.assertEqual(response_empty.unit, "km", "Empty unit should return unit = 'km'")

    # Tests adicionales eliminados para presentación más concisa


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)