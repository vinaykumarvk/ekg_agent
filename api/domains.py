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
    default_vectorstore_id: Optional[str] = None  # Document vector store ID
    kg_vectorstore_id: Optional[str] = None  # KG vector store ID (for KG node search)
    description: str = ""
    
    def get_kg_path(self) -> str:
        """
        Get KG path dynamically from environment variable.
        This ensures env vars are read at runtime, not at module load time.
        Raises ValueError if environment variable is not set.
        """
        env_var_name = f"{self.domain_id.upper()}_KG_PATH"
        env_path = os.getenv(env_var_name)
        if not env_path:
            raise ValueError(
                f"KG path not configured for domain '{self.domain_id}'. "
                f"Set {env_var_name} environment variable."
            )
        return env_path
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "description": self.description,
            "kg_path": self.get_kg_path(),  # Use dynamic getter
            "default_vectorstore_id": self.default_vectorstore_id,
            "kg_vectorstore_id": self.kg_vectorstore_id,
        }


def _get_vector_store_id(domain_id: str) -> str:
    """
    Get document vector store ID for a domain.
    For simplicity and consistency, we now always use DOC_VECTOR_STORE_ID
    (shared default). Domain-specific overrides are intentionally ignored to
    avoid drift between environments.
    
    Raises ValueError if DOC_VECTOR_STORE_ID is not configured.
    """
    doc_vs_id = os.getenv("DOC_VECTOR_STORE_ID") or settings.DOC_VECTOR_STORE_ID
    if doc_vs_id:
        return doc_vs_id
    
    # No fallback - fail explicitly
    raise ValueError(
        f"Vector store ID not configured for domain '{domain_id}'. "
        "Set DOC_VECTOR_STORE_ID environment variable."
    )


def _get_kg_vector_store_id() -> str:
    """
    Get KG vector store ID from environment variables or settings.
    Raises ValueError if not configured.
    
    In Google Cloud, this is injected from Secret Manager as an environment variable.
    """
    kg_vs_id = os.getenv("KG_VECTOR_STORE_ID") or settings.KG_VECTOR_STORE_ID
    if kg_vs_id:
        return kg_vs_id
    
    # No fallback - fail explicitly
    raise ValueError(
        "KG vector store ID not configured. Set KG_VECTOR_STORE_ID environment variable."
    )


# Registry of available domains
# Vector store IDs are read from environment variables (or .env file)
# In production (Google Cloud), these come from Secret Manager
# Note: kg_path defaults are only used for initialization - actual loading uses get_kg_path()
# which requires environment variables to be set
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path="",  # Will be read from WEALTH_MANAGEMENT_KG_PATH env var at runtime
        default_vectorstore_id=_get_vector_store_id("wealth_management"),
        kg_vectorstore_id=_get_kg_vector_store_id(),
        description="Mutual funds, orders, customer onboarding, and wealth management processes"
    ),
    "apf": DomainConfig(
        domain_id="apf",
        name="APF",
        kg_path="",  # Will be read from APF_KG_PATH env var at runtime
        default_vectorstore_id=_get_vector_store_id("apf"),
        kg_vectorstore_id=_get_kg_vector_store_id(),
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
