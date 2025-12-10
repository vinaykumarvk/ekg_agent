"""
Domain Registry for Multi-Tenant EKG Agent

Each domain represents a distinct subject area with its own:
- Knowledge graph (loaded from GCS)
- Default vector store (from DOC_VECTOR_STORE_ID or domain-specific override)
- Configuration parameters

All paths and IDs are configured via environment variables - no hardcoded values.
"""
from dataclasses import dataclass
from typing import Dict, Optional

from api.settings import settings


@dataclass
class DomainConfig:
    """Configuration for a specific domain/subject"""
    domain_id: str
    name: str
    kg_path: str
    default_vectorstore_id: str  # Required, no longer optional
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


def _get_domains() -> Dict[str, DomainConfig]:
    """
    Build domain registry from environment variables.
    All KG paths must be GCS paths (gs://...).
    Vector store IDs default to DOC_VECTOR_STORE_ID unless overridden.
    """
    return {
        "wealth_management": DomainConfig(
            domain_id="wealth_management",
            name="Wealth Management",
            kg_path=settings.WEALTH_MANAGEMENT_KG_PATH,  # GCS path from env
            default_vectorstore_id=(
                settings.WEALTH_MANAGEMENT_VECTOR_STORE_ID 
                or settings.DOC_VECTOR_STORE_ID  # Fallback to DOC_VECTOR_STORE_ID
            ),
            description="Mutual funds, orders, customer onboarding, and wealth management processes"
        ),
        "apf": DomainConfig(
            domain_id="apf",
            name="APF",
            kg_path=settings.APF_KG_PATH,  # GCS path from env
            default_vectorstore_id=(
                settings.APF_VECTOR_STORE_ID 
                or settings.DOC_VECTOR_STORE_ID  # Fallback to DOC_VECTOR_STORE_ID
            ),
            description="APF process data"
        ),
    }


# Initialize domains from environment variables
DOMAINS: Dict[str, DomainConfig] = _get_domains()


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

