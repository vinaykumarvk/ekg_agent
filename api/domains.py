"""
Domain Registry for Multi-Tenant EKG Agent

Each domain represents a distinct subject area with its own:
- Knowledge graph (local path or GCS path gs://bucket/path)
- Default vector store
- Configuration parameters

KG paths can be configured via environment variables:
- WEALTH_MANAGEMENT_KG_PATH: Path to wealth management KG (local or gs://)
- APF_KG_PATH: Path to APF KG (local or gs://)
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class DomainConfig:
    """Configuration for a specific domain/subject"""
    domain_id: str
    name: str
    kg_path: str  # Local path or GCS path (gs://bucket/path)
    default_vectorstore_id: Optional[str] = None  # Document vector store ID
    kg_vectorstore_id: Optional[str] = None  # KG vector store ID (for KG node search)
    description: str = ""
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "kg_path": self.kg_path,
            "default_vectorstore_id": self.default_vectorstore_id,
            "kg_vectorstore_id": self.kg_vectorstore_id,
        }


# Default KG paths (can be overridden by environment variables)
# For production, set env vars to GCS paths like: gs://your-bucket/kg/wealth_product_kg.json
DEFAULT_WEALTH_KG_PATH = "data/kg/wealth_product_kg.json"
DEFAULT_APF_KG_PATH = "data/kg/apf_kg.json"

# Registry of available domains
# Vector store IDs from docs/kg_vector_response_v2.py:
# DOC_VECTOR_STORE_ID = "vs_6910a0f29b548191befd180730d968ee" (for documents)
# KG_VECTOR_STORE_ID = "vs_6934751b8a90819190113fe85b689848" (for KG nodes)
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path=os.getenv("WEALTH_MANAGEMENT_KG_PATH", DEFAULT_WEALTH_KG_PATH),
        default_vectorstore_id="vs_6910a0f29b548191befd180730d968ee",  # DOC_VECTOR_STORE_ID
        kg_vectorstore_id="vs_6934751b8a90819190113fe85b689848",  # KG_VECTOR_STORE_ID
        description="Mutual funds, orders, customer onboarding, and wealth management processes"
    ),
    "apf": DomainConfig(
        domain_id="apf",
        name="APF",
        kg_path=os.getenv("APF_KG_PATH", DEFAULT_APF_KG_PATH),
        default_vectorstore_id="vs_6910a0f29b548191befd180730d968ee",  # DOC_VECTOR_STORE_ID (shared)
        kg_vectorstore_id="vs_6934751b8a90819190113fe85b689848",  # KG_VECTOR_STORE_ID (shared)
        description="APF process data"
    ),
}


def get_domain(domain_id: str) -> DomainConfig:
    """
    Get domain configuration by ID.
    
    Args:
        domain_id: Unique identifier for the domain
        
    Returns:
        DomainConfig for the requested domain
        
    Raises:
        ValueError: If domain_id is not registered
    """
    if domain_id not in DOMAINS:
        available = ", ".join(DOMAINS.keys())
        raise ValueError(
            f"Unknown domain: '{domain_id}'. Available domains: {available}"
        )
    return DOMAINS[domain_id]


def list_domains() -> list[DomainConfig]:
    """
    List all available domains.
    
    Returns:
        List of all registered DomainConfig objects
    """
    return list(DOMAINS.values())


def register_domain(config: DomainConfig) -> None:
    """
    Dynamically register a new domain.
    
    Args:
        config: DomainConfig to register
    """
    DOMAINS[config.domain_id] = config


def domain_exists(domain_id: str) -> bool:
    """
    Check if a domain is registered.
    
    Args:
        domain_id: Domain identifier to check
        
    Returns:
        True if domain exists, False otherwise
    """
    return domain_id in DOMAINS

