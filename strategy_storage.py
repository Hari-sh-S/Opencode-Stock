"""
Strategy Storage Module

Saves and loads strategy configurations to/from Hugging Face Datasets.
Strategies are stored in the 'hedge_model_strategies/' folder within the existing HF repo.
"""

import os
import json
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional
import tempfile
from pathlib import Path


def get_hf_credentials():
    """Get HF credentials from Streamlit secrets or environment."""
    try:
        # Try Streamlit secrets first
        token = st.secrets.get("HF_TOKEN")
        repo = st.secrets.get("HF_DATASET_REPO")
        if token and repo:
            return token, repo
    except Exception:
        pass
    
    # Fallback to environment variables
    token = os.getenv("HF_TOKEN")
    repo = os.getenv("HF_DATASET_REPO")
    return token, repo


def is_strategy_storage_configured() -> bool:
    """Check if HF is configured for strategy storage."""
    token, repo = get_hf_credentials()
    return bool(token and repo)


def _get_strategy_path(name: str) -> str:
    """Get the path within HF repo for a strategy file."""
    # Sanitize name for filename
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
    safe_name = safe_name.replace(" ", "_")
    return f"hedge_model_strategies/{safe_name}.json"


def save_strategy(name: str, config: Dict) -> bool:
    """
    Save a strategy configuration to Hugging Face.
    
    Args:
        name: User-friendly strategy name
        config: Dictionary containing all strategy parameters
        
    Returns:
        True if saved successfully
    """
    from huggingface_hub import upload_file
    
    token, repo = get_hf_credentials()
    if not token or not repo:
        st.error("Hugging Face not configured. Set HF_TOKEN and HF_DATASET_REPO.")
        return False
    
    try:
        # Add metadata
        strategy_data = {
            'name': name,
            'config': config,
            'created_at': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(strategy_data, f, indent=2, default=str)
            tmp_path = f.name
        
        # Upload to HF
        upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=_get_strategy_path(name),
            repo_id=repo,
            repo_type="dataset",
            token=token,
            commit_message=f"Save strategy: {name}"
        )
        
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)
        
        # Clear cache
        list_strategies.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error saving strategy: {e}")
        return False


def load_strategy(name: str) -> Optional[Dict]:
    """
    Load a strategy configuration from Hugging Face.
    
    Args:
        name: Strategy name to load
        
    Returns:
        Strategy config dictionary or None if not found
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError
    
    token, repo = get_hf_credentials()
    if not token or not repo:
        return None
    
    try:
        file_path = hf_hub_download(
            repo_id=repo,
            filename=_get_strategy_path(name),
            repo_type="dataset",
            token=token
        )
        
        with open(file_path, 'r') as f:
            strategy_data = json.load(f)
        
        return strategy_data.get('config', {})
        
    except EntryNotFoundError:
        return None
    except Exception as e:
        st.error(f"Error loading strategy: {e}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def list_strategies() -> List[str]:
    """
    List all saved strategy names from Hugging Face.
    
    Returns:
        List of strategy names (sorted alphabetically)
    """
    from huggingface_hub import list_repo_files
    
    token, repo = get_hf_credentials()
    if not token or not repo:
        return []
    
    try:
        files = list_repo_files(
            repo_id=repo,
            repo_type="dataset",
            token=token
        )
        
        # Extract strategy names from file paths
        strategies = []
        for f in files:
            if f.startswith("hedge_model_strategies/") and f.endswith(".json"):
                # Remove "hedge_model_strategies/" and ".json"
                name = f[23:-5].replace("_", " ")
                strategies.append(name)
        
        return sorted(strategies)
        
    except Exception as e:
        print(f"Error listing strategies: {e}")
        return []


def delete_strategy(name: str) -> bool:
    """
    Delete a strategy from Hugging Face.
    
    Args:
        name: Strategy name to delete
        
    Returns:
        True if deleted successfully
    """
    from huggingface_hub import HfApi
    
    token, repo = get_hf_credentials()
    if not token or not repo:
        return False
    
    try:
        api = HfApi(token=token)
        api.delete_file(
            path_in_repo=_get_strategy_path(name),
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Delete strategy: {name}"
        )
        
        # Clear cache
        list_strategies.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error deleting strategy: {e}")
        return False
