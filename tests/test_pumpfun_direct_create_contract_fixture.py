import hashlib
import json
import struct
from pathlib import Path


FIXTURE = (
    Path(__file__).parent / "fixtures" / "pumpfun_direct_create_contract.json"
)
PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode(value: str) -> bytes:
    number = 0
    for char in value:
        number = number * 58 + ALPHABET.index(char)
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(value) - len(value.lstrip("1"))) + raw


def _b58encode(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(b"\x00"))) + (encoded or "1")


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    end = offset + length
    return data[offset:end].decode("utf-8"), end


def _decode_create(fixture: dict, tx: dict) -> dict:
    assert tx["version"] in fixture["supported_transaction_versions"]
    assert tx["meta"]["err"] is None
    assert tx["blockTime"] is not None

    message = tx["transaction"]["message"]
    loaded = tx["meta"]["loadedAddresses"]
    keys = (
        message["accountKeys"]
        + loaded["writable"]
        + loaded["readonly"]
    )
    matches = []
    for instruction in message["instructions"]:
        if keys[instruction["programIdIndex"]] != fixture["program_id"]:
            continue
        data = _b58decode(instruction["data"])
        if data[:8].hex() != fixture["create"]["discriminator_hex"]:
            continue
        matches.append((instruction, data))
    assert len(matches) == 1

    instruction, data = matches[0]
    assert len(instruction["accounts"]) == len(fixture["create"]["accounts"])
    offset = 8
    name, offset = _read_string(data, offset)
    symbol, offset = _read_string(data, offset)
    uri, offset = _read_string(data, offset)
    creator = data[offset : offset + 32]
    offset += 32
    assert offset == len(data)
    accounts = [keys[index] for index in instruction["accounts"]]
    return {
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "mint": accounts[0],
        "bonding_curve": accounts[2],
        "associated_bonding_curve": accounts[3],
        "creator_address": _b58encode(creator),
        "signature": tx["transaction"]["signatures"][0],
        "slot": tx["slot"],
        "block_time": tx["blockTime"],
    }


def _decode_supported_event(fixture: dict) -> dict:
    data = bytes.fromhex(fixture["supported_event_data_hex"])
    assert data[:8].hex() == fixture["create_event"]["cpi_wrapper_hex"]
    assert data[8:16].hex() == fixture["create_event"]["discriminator_hex"]
    offset = 16
    name, offset = _read_string(data, offset)
    symbol, offset = _read_string(data, offset)
    uri, offset = _read_string(data, offset)
    pubkeys = []
    for _ in range(4):
        pubkeys.append(_b58encode(data[offset : offset + 32]))
        offset += 32
    timestamp = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    reserves = struct.unpack_from("<QQQQ", data, offset)
    offset += 32
    token_program = _b58encode(data[offset : offset + 32])
    offset += 32
    is_mayhem_mode = bool(data[offset])
    is_cashback_enabled = bool(data[offset + 1])
    offset += 2
    quote_mint = _b58encode(data[offset : offset + 32])
    offset += 32
    virtual_quote_reserves = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    assert offset == len(data)
    return {
        "name": name,
        "symbol": symbol,
        "uri": uri,
        "mint": pubkeys[0],
        "bonding_curve": pubkeys[1],
        "user": pubkeys[2],
        "creator": pubkeys[3],
        "timestamp": timestamp,
        "reserves": reserves,
        "token_program": token_program,
        "is_mayhem_mode": is_mayhem_mode,
        "is_cashback_enabled": is_cashback_enabled,
        "quote_mint": quote_mint,
        "virtual_quote_reserves": virtual_quote_reserves,
    }


def test_pinned_contract_and_create_field_extraction():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["program_id"] == PROGRAM_ID
    assert fixture["official_repository_commit"] == (
        "9c82f61cb711b044a17f770ab8ce9f9bdf78f333"
    )
    assert fixture["official_idl_sha256"] == (
        "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"
    )
    assert fixture["create"]["discriminator_hex"] == "181ec828051c0777"
    assert fixture["supported_transaction_versions"] == ["legacy", 0]
    case = fixture["valid_create_transaction"]
    assert _decode_create(fixture, case) == case["expected"]


def test_supported_event_layout_and_instruction_match():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event = _decode_supported_event(fixture)
    expected = fixture["valid_create_transaction"]["expected"]
    assert event["name"] == expected["name"]
    assert event["symbol"] == expected["symbol"]
    assert event["uri"] == expected["uri"]
    assert event["mint"] == expected["mint"]
    assert event["bonding_curve"] == expected["bonding_curve"]
    assert event["creator"] == expected["creator_address"]
    assert event["timestamp"] == expected["block_time"]
    assert event["reserves"] == (1000, 2000, 3000, 4000)
    assert event["is_mayhem_mode"] is False
    assert event["is_cashback_enabled"] is True
    assert event["virtual_quote_reserves"] == 5000
    assert len(fixture["create_event"]["fields"]) == 17


def test_fail_closed_contract_mutations():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = fixture["valid_create_transaction"]

    failed = json.loads(json.dumps(case))
    failed["meta"]["err"] = {"InstructionError": [0, "Custom"]}
    try:
        _decode_create(fixture, failed)
    except AssertionError:
        pass
    else:
        raise AssertionError("failed transaction was accepted")

    wrong_program = json.loads(json.dumps(case))
    wrong_program["transaction"]["message"]["accountKeys"][13] = (
        "11111111111111111111111111111111"
    )
    try:
        _decode_create(fixture, wrong_program)
    except AssertionError:
        pass
    else:
        raise AssertionError("wrong program was accepted")

    unsupported = json.loads(json.dumps(case))
    unsupported["version"] = 1
    try:
        _decode_create(fixture, unsupported)
    except AssertionError:
        pass
    else:
        raise AssertionError("unsupported transaction version was accepted")

    malformed = json.loads(json.dumps(case))
    malformed["transaction"]["message"]["instructions"][0]["accounts"].pop()
    try:
        _decode_create(fixture, malformed)
    except AssertionError:
        pass
    else:
        raise AssertionError("malformed account order was accepted")

    assert hashlib.sha256(
        bytes.fromhex(fixture["supported_event_data_hex"])
    ).hexdigest()
