from geopyspark.tests.python_test_utils import add_spark_path
add_spark_path()

from pyspark import SparkContext, RDD
from pyspark.serializers import AutoBatchedSerializer
from py4j.java_gateway import java_import
from geopyspark.avroserializer import AvroSerializer
from geopyspark.geotrellis.extent import Extent
from geopyspark.geotrellis.tile import TileArray
from geopyspark.avroregistry import AvroRegistry

import numpy as np
import unittest
import pytest


class KeyValueRecordSchemaTest(unittest.TestCase):
    def setUp(self):
        self.pysc = SparkContext(master="local[*]", appName="key-value-test")
        path = "geopyspark.geotrellis.tests.schemas.KeyValueRecordWrapper"
        java_import(self.pysc._gateway.jvm, path)

        self.extents = [Extent(0, 0, 1, 1), Extent(1, 2, 3, 4), Extent(5, 6, 7, 8)]
        self.arrs = [
                TileArray(np.array(bytearray([0, 1, 2, 3, 4, 5])).reshape(3, 2), -128),
                TileArray(np.array(bytearray([0, 1, 2, 3, 4, 5])).reshape(2, 3), -128),
                TileArray(np.array(bytearray([0, 1, 2, 3, 4, 5])).reshape(6, 1), -128)
                ]

        self.tuple_list= [
                (self.arrs[0], self.extents[0]),
                (self.arrs[1], self.extents[1]),
                (self.arrs[2], self.extents[2])
                ]

    @pytest.fixture(autouse=True)
    def tearDown(self):
        yield
        self.pysc.stop()
        self.pysc._gateway.close()

    def get_rdd(self):
        sc = self.pysc._jsc.sc()
        ew = self.pysc._gateway.jvm.KeyValueRecordWrapper

        tup = ew.testOut(sc)
        (java_rdd, schema) = (tup._1(), tup._2())

        ser = AvroSerializer(schema)
        return (RDD(java_rdd, self.pysc, AutoBatchedSerializer(ser)), schema)

    def get_kvs(self):
        (kvs, schema) = self.get_rdd()

        return kvs.collect()

    def test_encoded_kvs(self):
        (rdd, schema) = self.get_rdd()

        encoded = rdd.map(lambda s: AvroRegistry().key_value_record_encoder(s))

        actual_encoded = encoded.collect()

        pairs = [AvroRegistry.tuple_encoder(x,
            AvroRegistry.tile_encoder,
            AvroRegistry.extent_encoder) for x in self.tuple_list]

        expected_encoded = [
                {'pairs': pairs},
                {'pairs': pairs},
                ]

        self.assertEqual(actual_encoded, expected_encoded)

    def test_decoded_kvs(self):
        actual_kvs = self.get_kvs()

        expected_kvs = [
                self.tuple_list,
                self.tuple_list
                ]

        for actual_tuples, expected_tuples in zip(actual_kvs, expected_kvs):
            for actual, expected in zip(actual_tuples, expected_tuples):
                (actual_tile, actual_extent) = actual
                (expected_tile, expected_extent) = expected

                self.assertTrue((actual_tile == expected_tile).all())
                self.assertEqual(actual_extent, expected_extent)


if __name__ == "__main__":
    unittest.main()