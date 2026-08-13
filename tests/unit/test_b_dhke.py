from acorn.b_dhke import hash_to_curve


def test_hash_to_curve_matches_cashu_nut00_reference_vectors():
    vectors = {
        "00" * 32: "024cce997d3b518f739663b757deaec95bcd9473c30a14ac2fd04023a739d1a725",
        ("00" * 31) + "01": "022e7158e11c9506f1aa4248bf531298daa7febd6194f003edcd9b93ade6253acf",
        ("00" * 31) + "02": "026cdbe15362df59cd1dd3c9c11de8aedac2106eca69236ecd9fbe117af897be4f",
    }

    for secret_hex, expected_y in vectors.items():
        assert hash_to_curve(bytes.fromhex(secret_hex)).serialize().hex() == expected_y
