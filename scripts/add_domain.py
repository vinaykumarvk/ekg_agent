#!/usr/bin/env python3
"""
Helper script to add a new domain to the EKG Agent.

Usage:
    python scripts/add_domain.py
    
This script will guide you through adding a new domain configuration.
"""
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    print("=" * 70)
    print("Add New Domain to EKG Agent")
    print("=" * 70)
    print()
    
    # Collect domain information
    print("Enter domain information:")
    domain_id = input("Domain ID (e.g., 'healthcare'): ").strip()
    if not domain_id:
        print("Error: Domain ID is required")
        return 1
    
    name = input("Display Name (e.g., 'Healthcare Systems'): ").strip()
    if not name:
        print("Error: Display name is required")
        return 1
    
    kg_path = input("KG file path (e.g., 'data/kg/healthcare_kg.json'): ").strip()
    if not kg_path:
        print("Error: KG path is required")
        return 1
    
    default_vs = input("Default vector store ID (optional): ").strip() or None
    description = input("Description (optional): ").strip()
    
    # Generate the code to add
    code = f'''
# Add to api/domains.py DOMAINS dict:

    "{domain_id}": DomainConfig(
        domain_id="{domain_id}",
        name="{name}",
        kg_path="{kg_path}",
        default_vectorstore_id={f'"{default_vs}"' if default_vs else 'None'},
        description="{description}"
    ),
'''
    
    print()
    print("=" * 70)
    print("Configuration Generated")
    print("=" * 70)
    print()
    print("Add the following to api/domains.py in the DOMAINS dictionary:")
    print(code)
    print()
    print("Steps to complete:")
    print("1. Place your KG JSON file at:", kg_path)
    print("2. Add the above configuration to api/domains.py")
    print("3. Restart the server")
    print("4. Test with: curl http://localhost:8000/domains")
    print()
    
    # Check if KG file exists
    if not os.path.isabs(kg_path):
        full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), kg_path)
    else:
        full_path = kg_path
    
    if os.path.exists(full_path):
        print(f"✓ KG file found at {full_path}")
    else:
        print(f"⚠️  KG file not found at {full_path}")
        print(f"   You need to upload your KG file to this location")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())



