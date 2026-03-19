#!/usr/bin/env python3
"""
Test script to verify rate limiting is working.
Sends 15 requests to a rate-limited endpoint (limit is 10/60s).
"""
import requests
import time

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/auth/login"

print(f"Testing rate limiter on {ENDPOINT}")
print(f"Current limit: 10 requests per 60 seconds")
print(f"Sending 15 requests...\n")

for i in range(1, 16):
    try:
        response = requests.post(
            ENDPOINT,
            data={
                "username": "test@example.com",
                "password": "wrongpassword"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        status = response.status_code
        
        if status == 429:
            print(f"Request {i}: ❌ RATE LIMITED (429) - Rate limiter working!")
            print(f"   Response: {response.json()}")
        elif status in [401, 422]:
            print(f"Request {i}: ✅ Allowed ({status}) - Auth failed but not rate limited")
        else:
            print(f"Request {i}: Status {status} - {response.text[:100]}")
        
        time.sleep(0.2)  # Small delay between requests
        
    except Exception as e:
        print(f"Request {i}: Error - {e}")

print("\n✅ Test complete. If you see 429 errors after request 10, rate limiting is working!")
