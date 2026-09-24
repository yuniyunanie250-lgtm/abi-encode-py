import unittest

from abi_encode import AbiError, decode_words, encode, encode_call, encode_word, word


class Words(unittest.TestCase):
    def test_one_ether_is_the_expected_word(self):
        self.assertEqual(
            word(10 ** 18).hex(),
            "0000000000000000000000000000000000000000000000000de0b6b3a7640000",
        )

    def test_negative_is_refused(self):
        with self.assertRaises(AbiError):
            word(-1)

    def test_two_to_the_256_is_refused(self):
        with self.assertRaises(AbiError):
            word(1 << 256)

    def test_two_to_the_256_minus_one_is_allowed(self):
        self.assertEqual(word((1 << 256) - 1), b"\xff" * 32)


class Static(unittest.TestCase):
    def test_address_lands_in_the_low_twenty_bytes(self):
        out = encode_word("address", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
        self.assertEqual(out[:12], b"\x00" * 12)
        self.assertEqual(out[12:].hex(), "d8da6bf26964af9d7eed9e03e53415d37aa96045")

    def test_address_must_be_twenty_bytes(self):
        with self.assertRaises(AbiError):
            encode_word("address", "0x1234")

    def test_bool_accepts_python_and_string_forms(self):
        self.assertEqual(encode_word("bool", True)[31], 1)
        self.assertEqual(encode_word("bool", "false")[31], 0)

    def test_uint8_range_is_checked(self):
        self.assertEqual(encode_word("uint8", "255")[-1], 255)
        with self.assertRaises(AbiError):
            encode_word("uint8", "256")

    def test_int_is_twos_complemented(self):
        self.assertEqual(encode_word("int256", "-1"), b"\xff" * 32)

    def test_int8_bounds(self):
        self.assertEqual(encode_word("int8", "-128")[-1], 128)
        with self.assertRaises(AbiError):
            encode_word("int8", "128")

    def test_bytes4_must_be_exactly_four_bytes(self):
        self.assertEqual(
            encode_word("bytes4", "0xa9059cbb").hex(),
            "a9059cbb" + "00" * 28,
        )
        with self.assertRaises(AbiError):
            encode_word("bytes4", "0xa9059cbb00")

    def test_unknown_type_is_refused(self):
        with self.assertRaises(AbiError):
            encode_word("tuple", "1")


class Layout(unittest.TestCase):
    def test_two_static_args_are_two_words(self):
        out = encode([
            ("address", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"),
            ("uint256", "1000000000000000000"),
        ])
        self.assertEqual(len(out), 64)

    def test_a_string_is_offset_then_length_then_data(self):
        out = encode([("string", "hello")])
        self.assertEqual(out[:32].hex(), "00" * 31 + "20")
        self.assertEqual(out[32:64].hex(), "00" * 31 + "05")
        self.assertEqual(out[64:69], b"hello")
        self.assertEqual(len(out), 96)

    def test_offsets_are_measured_from_the_argument_block(self):
        # the offset must NOT include the 4-byte selector
        call = encode_call("0xa9059cbb", [("string", "hi")])
        raw = bytes.fromhex(call[10:])  # drop 0x + selector
        self.assertEqual(int.from_bytes(raw[:32], "big"), 32)

    def test_a_static_arg_before_a_dynamic_one_shifts_the_offset(self):
        out = encode([("uint256", "1"), ("string", "hi")])
        self.assertEqual(int.from_bytes(out[:32], "big"), 1)
        self.assertEqual(int.from_bytes(out[32:64], "big"), 64)

    def test_uint_array_is_length_prefixed(self):
        out = encode([("uint256[]", [1, 2])])
        self.assertEqual(out[:32].hex(), "00" * 31 + "20")
        self.assertEqual(out[32:64].hex(), "00" * 31 + "02")
        self.assertEqual(len(out), 128)

    def test_length_is_in_bytes_not_characters(self):
        self.assertEqual(len(encode([("string", "hello")])), 96)

    def test_empty_string_still_has_a_length_word(self):
        self.assertEqual(len(encode([("string", "")])), 64)

    def test_nested_dynamic_arrays_are_refused(self):
        with self.assertRaises(AbiError):
            encode([("string[]", ["a"])])

    def test_decode_words_round_trips_a_static_block(self):
        out = encode([("uint256", "7")])
        self.assertEqual(int.from_bytes(decode_words(out)[0], "big"), 7)

    def test_decode_words_rejects_a_partial_word(self):
        with self.assertRaises(AbiError):
            decode_words("0x1234")

    def test_selector_must_be_four_bytes(self):
        with self.assertRaises(AbiError):
            encode_call("0xa9059c", [])


class EndToEnd(unittest.TestCase):
    def test_a_real_transfer_calldata(self):
        call = encode_call("0xa9059cbb", [
            ("address", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"),
            ("uint256", "1000000000000000000"),
        ])
        self.assertTrue(call.startswith("0xa9059cbb"))
        self.assertEqual(len(call), 2 + 8 + 128)
        self.assertTrue(call.endswith("0de0b6b3a7640000"))


if __name__ == "__main__":
    unittest.main()
