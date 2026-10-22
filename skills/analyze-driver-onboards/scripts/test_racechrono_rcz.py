#!/usr/bin/env python3
"""Synthetic safety/semantics checks. Real export cross-checks use --verify-csv."""
import csv
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from racechrono_rcz import MISSING_I32, read_rcz, verify_csv


class RczTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.t = 1700000000000
        self.meta = {"version": 1, "firstTimestamp": self.t, "latestTimestamp": self.t+2000,
                     "lengthDistance": 20000, "firstPositionLatitude": -60000000,
                     "firstPositionLongitude": -462000000, "lapCount": 1,
                     "laps": [{"number": 1, "startTimestamp": self.t, "finishTimestamp": self.t+1500,
                               "sessionResume": 0, "isInvalid": False},
                              {"number": 2, "startTimestamp": self.t+1500, "sessionResume": 0}]}
        self.fragment = {"version": 1, "primaryGpsDeviceIndex": 300,
                         "devices2": [{"selector": {"id": 300, "type": 1}}]}
        self.channels = {
            "channel_1_300_0_1_1": struct.pack("<3q", self.t, self.t+1000, self.t+2000),
            "channel_1_300_0_2_1": struct.pack("<3q", 0, 10000, 20000),
            "channel_1_300_0_3_1": struct.pack("<6i", -60000000, -462000000, -60000500, -462000000,
                                             -60001000, -462000000),
            "channel_1_300_0_4_0": struct.pack("<3i", 10000, 20000, 30000),
            "channel_1_300_0_5_0": struct.pack("<3i", 400000, 400100, 400200),
            "channel_1_300_0_6_0": struct.pack("<3i", MISSING_I32, 180000, 180000),
            "channel_1_300_0_30007_0": struct.pack("<3i", 2000, 2000, 2000),
            "channel_1_300_0_30003_0": struct.pack("<3i", 1, 1, 1),
        }

    def archive(self, extra=None):
        p = self.root / "synthetic.rcz"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("session.json", json.dumps(self.meta))
            z.writestr("sessionfragment.json", json.dumps(self.fragment))
            for n, v in {**self.channels, **(extra or {})}.items():
                z.writestr(n, v)
        return p

    def test_signed_coordinates_scaling_primary_id_and_incomplete_lap(self):
        d = read_rcz(self.archive())
        self.assertEqual(d["samples"][0]["latitude_deg"], -10)
        self.assertEqual(d["samples"][0]["longitude_deg"], -77)
        self.assertEqual(d["samples"][1]["speed_mps"], 20)
        self.assertEqual(d["samples"][2]["distance_m"], 20)
        self.assertEqual(d["samples"][0]["altitude_m"], 400)
        self.assertEqual(d["laps"][0]["lap_time_s"], 1.5)
        self.assertIsNone(d["laps"][1]["lap_time_s"])
        self.assertEqual(d["samples"][2]["lap_number"], 2)
        self.assertEqual(d["audit"]["primary_gps_device_id"], 300)

    def test_missing_bearing_and_position_are_not_zeros(self):
        self.channels["channel_1_300_0_3_1"] = struct.pack("<6i", MISSING_I32, -462000000,
                                                         -60000500, -462000000, -60001000, -462000000)
        d = read_rcz(self.archive())
        self.assertIsNone(d["samples"][0]["bearing_deg"])
        self.assertIsNone(d["samples"][0]["latitude_deg"])
        self.assertIsNone(d["samples"][0]["longitude_deg"])

    def test_unequal_channel_lengths_rejected(self):
        self.channels["channel_1_300_0_4_0"] = struct.pack("<2i", 1000, 2000)
        with self.assertRaisesRegex(ValueError, "lengths differ"):
            read_rcz(self.archive())

    def test_truncated_binary_rejected(self):
        self.channels["channel_1_300_0_4_0"] = b"bad"
        with self.assertRaisesRegex(ValueError, "byte length"):
            read_rcz(self.archive())

    def test_duplicate_and_backwards_timestamps_rejected(self):
        for middle in [self.t, self.t-1]:
            self.channels["channel_1_300_0_1_1"] = struct.pack("<3q", self.t, middle, self.t+2000)
            with self.assertRaisesRegex(ValueError, "repeat or go backwards"):
                read_rcz(self.archive())

    def test_clock_uses_first_sample_not_created_time(self):
        self.meta["timeCreated"] = self.t-6500
        d = read_rcz(self.archive())
        self.assertEqual(d["samples"][0]["elapsed_time_s"], 0)

    def test_resumes_rejected(self):
        self.meta["laps"][0]["sessionResume"] = 1
        with self.assertRaisesRegex(ValueError, "Resumed sessions"):
            read_rcz(self.archive())

    def test_unknown_stream_rejected(self):
        self.channels["channel_2_300_0_4_0"] = self.channels.pop("channel_1_300_0_4_0")
        with self.assertRaisesRegex(ValueError, "Unsupported channel stream"):
            read_rcz(self.archive())

    def test_unknown_channel_is_inventoried_without_guessing_units(self):
        d = read_rcz(self.archive({"channel_1_300_0_12345_0": struct.pack("<3i", 9, 8, 7)}))
        self.assertFalse(d["audit"]["channel_inventory"][-1]["decoded"])
        self.assertNotIn("throttle_pct", d["samples"][0])

    def test_alternative_encoding_rejected(self):
        self.channels["channel_1_300_0_4_3"] = self.channels.pop("channel_1_300_0_4_0")
        with self.assertRaisesRegex(ValueError, "Unsupported encoding"):
            read_rcz(self.archive())

    def test_unsafe_and_nested_paths_rejected(self):
        for path in ["../untrusted.txt", "/absolute", "sessions/other/session.json"]:
            with self.assertRaises(ValueError):
                read_rcz(self.archive({path: b"x"}))

    def test_duplicate_zip_member_rejected(self):
        p = self.archive()
        with self.assertWarns(UserWarning), zipfile.ZipFile(p, "a") as z:
            z.writestr("session.json", "{}")
        with self.assertRaisesRegex(ValueError, "Duplicate ZIP"):
            read_rcz(p)

    def test_oversize_archive_rejected(self):
        with self.assertRaisesRegex(ValueError, "size limit"):
            read_rcz(self.archive(), max_uncompressed_bytes=10)

    def test_distance_reset_rejected(self):
        self.channels["channel_1_300_0_2_1"] = struct.pack("<3q", 0, 10000, 0)
        with self.assertRaisesRegex(ValueError, "distance resets"):
            read_rcz(self.archive())

    def test_csv_duplicate_speed_names_select_source_and_detect_wrong_values(self):
        d = read_rcz(self.archive())
        p = self.root / "synthetic_v3.csv"
        rows = [["Format", "3"],
                ["timestamp", "distance_traveled", "latitude", "longitude", "speed", "speed", "altitude", "bearing", "accuracy", "fix_type"],
                ["unix time", "m", "deg", "deg", "m/s", "m/s", "m", "deg", "m", ""],
                ["", "", "300: gps", "300: gps", "calc", "300: gps", "300: gps", "300: gps", "300: gps", "300: gps"]]
        for s in d["samples"]:
            rows.append([s["timestamp_ms"]/1000, s["distance_m"], round(s["latitude_deg"], 7),
                         round(s["longitude_deg"], 7), 999, s["speed_mps"], s["altitude_m"],
                         s["bearing_deg"], s["accuracy_m"], s["fix_type"]])
        def write():
            with p.open("w", newline="") as f:
                csv.writer(f).writerows(rows)
        write()
        self.assertTrue(verify_csv(d, p)["passed"])
        rows[-1][5] = 999
        write()
        self.assertFalse(verify_csv(d, p)["passed"])
        rows[3][5] = "calc"
        write()
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous"):
            verify_csv(d, p)


if __name__ == "__main__":
    unittest.main()
