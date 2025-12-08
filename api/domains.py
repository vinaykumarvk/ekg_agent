"""
Domain Registry for Multi-Tenant EKG Agent

Each domain represents a distinct subject area with its own:
- Knowledge graph
- Default vector store (from environment variables or Secret Manager)
- Configuration parameters

Vector Store IDs are read from environment variables (or .env file locally):
- DOC_VECTOR_STORE_ID: Default document vector store (shared)
- KG_VECTOR_STORE_ID: Knowledge Graph vector store
- WEALTH_MANAGEMENT_VECTOR_STORE_ID: Override for wealth_management domain
- APF_VECTOR_STORE_ID: Override for apf domain

In Google Cloud, these can be set via Secret Manager and will be injected as environment variables.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional
from api.settings import settings


@dataclass
class DomainConfig:
    """Configuration for a specific domain/subject"""
    domain_id: str
    name: str
    kg_path: str
    default_vectorstore_id: Optional[str] = None
    description: str = ""
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "kg_path": self.kg_path,
            "default_vectorstore_id": self.default_vectorstore_id,
        }


def _get_vector_store_id(domain_id: str) -> Optional[str]:
    """
    Get vector store ID for a domain from environment variables or settings.
    Priority:
    1. Domain-specific env var (e.g., WEALTH_MANAGEMENT_VECTOR_STORE_ID)
    2. DOC_VECTOR_STORE_ID (shared default)
    3. None (will cause error if domain requires it)
    
    In Google Cloud, these are injected from Secret Manager as environment variables.
    """
    # Try domain-specific override first
    domain_env_var = f"{domain_id.upper()}_VECTOR_STORE_ID"
    domain_id_value = os.getenv(domain_env_var) or getattr(settings, domain_env_var, None)
    if domain_id_value:
        return domain_id_value
    
    # Fall back to shared DOC_VECTOR_STORE_ID
    doc_vs_id = os.getenv("DOC_VECTOR_STORE_ID") or settings.DOC_VECTOR_STORE_ID
    return doc_vs_id


# Registry of available domains
# Vector store IDs are read from environment variables (or .env file)
# In production (Google Cloud), these come from Secret Manager
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path=os.getenv("WEALTH_MANAGEMENT_KG_PATH", "data/kg/wealth_product_kg.json"),
        default_vectorstore_id=_get_vector_store_id("wealth_management"),
        description="Mutual funds, orders, customer onboarding, and wealth management processes"
    ),
    "apf": DomainConfig(
        domain_id="apf",
        name="APF",
        kg_path=os.getenv("APF_KG_PATH", "data/kg/apf_kg.json"),
        default_vectorstore_id=_get_vector_store_id("apf"),
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
