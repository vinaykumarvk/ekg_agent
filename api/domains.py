"""
Domain Registry for Multi-Tenant EKG Agent

Each domain represents a distinct subject area with its own:
- Knowledge graph
- Default vector store
- Configuration parameters
"""
from dataclasses import dataclass
from typing import Dict, Optional


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


# Registry of available domains
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path="data/kg/wealth_product_kg.json",
        default_vectorstore_id="vs_689b49252a4c8191a12a1528a475fbd8",
        description="Mutual funds, orders, customer onboarding, and wealth management processes"
    ),
    "apf": DomainConfig(
        domain_id="apf",
        name="APF",
        kg_path="data/kg/apf_kg.json",
        default_vectorstore_id="vs_68ea1f9e59b8819193d3c092779bb47e",
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

