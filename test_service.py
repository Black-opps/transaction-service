"""
Test script to verify Transaction Service is working
"""

import json

import requests

BASE_URL = "http://localhost:8006"


def test_health():
    """Test health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health: {response.status_code} - {response.json()}")
    return response.status_code == 200


def test_create_transactions():
    """Test batch transaction creation"""
    test_transactions = {
        "tenant_id": "default",
        "transactions": [
            {
                "transaction_id": "TEST_TXN_001",
                "hash_key": "test_hash_001",
                "date": "2026-05-17T10:00:00",
                "amount": 2500.00,
                "transaction_type": "sent",
                "counterparty": "Test Merchant",
                "description": "Test transaction",
                "reference": "REF001",
            },
            {
                "transaction_id": "TEST_TXN_002",
                "hash_key": "test_hash_002",
                "date": "2026-05-17T11:00:00",
                "amount": 5000.00,
                "transaction_type": "received",
                "counterparty": "Test Customer",
                "description": "Test payment",
                "reference": "REF002",
            },
        ],
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/transactions/batch", json=test_transactions
    )
    print(f"Batch create: {response.status_code} - {response.json()}")
    return response.status_code == 200


def test_get_transactions():
    """Test GET transactions endpoint"""
    response = requests.get(
        f"{BASE_URL}/api/v1/transactions", params={"tenant_id": "default", "limit": 10}
    )
    print(f"Get transactions: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Total: {data.get('total')} transactions")
    return response.status_code == 200


def test_get_stats():
    """Test GET stats endpoint"""
    response = requests.get(
        f"{BASE_URL}/api/v1/transactions/stats", params={"tenant_id": "default"}
    )
    print(f"Get stats: {response.status_code}")
    if response.status_code == 200:
        stats = response.json()
        print(f"  Money In: {stats.get('total_money_in')}")
        print(f"  Money Out: {stats.get('total_money_out')}")
        print(f"  Net Flow: {stats.get('net_flow')}")
    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Transaction Service")
    print("=" * 50)

    tests = [
        ("Health Check", test_health),
        ("Create Transactions", test_create_transactions),
        ("Get Transactions", test_get_transactions),
        ("Get Stats", test_get_stats),
    ]

    for name, test_func in tests:
        print(f"\n📋 Running: {name}")
        try:
            if test_func():
                print(f"  ✅ {name} passed")
            else:
                print(f"  ❌ {name} failed")
        except Exception as e:
            print(f"  ❌ {name} error: {e}")
