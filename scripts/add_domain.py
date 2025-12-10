#!/usr/bin/env python3
"""
Helper script to add a new domain to the EKG Agent.

Usage:
    python scripts/add_domain.py
    
This script will guide you through adding a new domain configuration.

IMPORTANT: All KG files must be stored in Google Cloud Storage (GCS).
Local file paths are NOT supported.
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
    print("IMPORTANT: All KG files must be stored in GCS (gs://bucket/path)")
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
    
    kg_path = input("GCS KG file path (e.g., 'gs://my-bucket/kg/healthcare_kg.json'): ").strip()
    if not kg_path:
        print("Error: KG path is required")
        return 1
    if not kg_path.startswith("gs://"):
        print("Error: KG path must be a GCS path starting with 'gs://'")
        return 1
    
    description = input("Description (optional): ").strip()
    
    # Generate environment variable name
    env_var_name = f"{domain_id.upper()}_KG_PATH"
    vs_env_var_name = f"{domain_id.upper()}_VECTORSTORE_ID"
    
    # Generate the code to add
    settings_code = f'''
# Add to api/settings.py in the Settings class:

    {env_var_name}: str = Field(
        ...,  # Required - no default
        description="GCS path to {name} KG"
    )
    {vs_env_var_name}: str | None = None  # Optional override
'''

    domains_code = f'''
# Add to api/domains.py in _get_domains() function:

        "{domain_id}": DomainConfig(
            domain_id="{domain_id}",
            name="{name}",
            kg_path=settings.{env_var_name},  # GCS path from env
            default_vectorstore_id=(
                settings.{vs_env_var_name} 
                or settings.DOC_VECTORSTORE_ID  # Fallback to DOC_VECTORSTORE_ID
            ),
            description="{description}"
        ),
'''

    env_example = f'''
# Add to .env or Cloud Run environment:

{env_var_name}={kg_path}
# {vs_env_var_name}=vs_optional_override  # Optional
'''
    
    print()
    print("=" * 70)
    print("Configuration Generated")
    print("=" * 70)
    print()
    print("1. Add to api/settings.py:")
    print(settings_code)
    print()
    print("2. Add to api/domains.py:")
    print(domains_code)
    print()
    print("3. Add environment variables:")
    print(env_example)
    print()
    print("Steps to complete:")
    print(f"1. Upload your KG JSON file to GCS: {kg_path}")
    print("2. Add the settings configuration above")
    print("3. Add the domain configuration above")
    print("4. Set the environment variable")
    print("5. Restart the server")
    print("6. Test with: curl http://localhost:8000/domains")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())



