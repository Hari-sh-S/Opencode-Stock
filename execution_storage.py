"""
Execution Storage Module

Saves and loads executed strategy data to/from Hugging Face Datasets.
Executions are stored in the 'executions/' folder within the existing HF repo.
"""

import os
import json
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional
import tempfile
from pathlib import Path


def _get_hf_credentials():
    """Get HF credentials from Streamlit secrets or environment."""
    try:
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


def is_execution_storage_configured() -> bool:
    """Check if HF is configured for execution storage."""
    token, repo = _get_hf_credentials()
    return bool(token and repo)


def _get_execution_path(name: str) -> str:
    """Get the path within HF repo for an execution file."""
    # Sanitize name for filename
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
    safe_name = safe_name.replace(" ", "_")
    return f"executions/{safe_name}.json"


def save_execution(
    name: str,
    strategy_template: str,
    mode: str,  # 'paper' or 'live'
    capital: float,
    trades: List[Dict],
    portfolio_values: List[Dict],
    open_positions: List[Dict] = None,
    notes: str = "",
    tags: List[str] = None
) -> bool:
    """
    Save an execution to Hugging Face.
    
    Args:
        name: User-friendly execution name
        strategy_template: Name of the strategy template used
        mode: 'paper' or 'live'
        capital: Initial capital
        trades: List of trade dictionaries
        portfolio_values: List of {date, value} dictionaries
        open_positions: Current open positions
        notes: Optional notes about this execution
        tags: Optional list of tags for categorisation
        
    Returns:
        True if saved successfully
    """
    from huggingface_hub import upload_file
    
    token, repo = _get_hf_credentials()
    if not token or not repo:
        st.error("Hugging Face not configured. Set HF_TOKEN and HF_DATASET_REPO.")
        return False
    
    try:
        now = datetime.now().isoformat()
        
        execution_data = {
            'name': name,
            'strategy_template': strategy_template,
            'mode': mode,
            'capital': capital,
            'created_at': now,
            'last_updated': now,
            'trades': trades,
            'portfolio_values': portfolio_values,
            'open_positions': open_positions or [],
            'notes': notes,
            'tags': tags or [],
            'version': '1.0'
        }
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(execution_data, f, indent=2, default=str)
            tmp_path = f.name
        
        # Upload to HF
        upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=_get_execution_path(name),
            repo_id=repo,
            repo_type="dataset",
            token=token,
            commit_message=f"Save execution: {name}"
        )
        
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)
        
        # Clear cache
        list_executions.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error saving execution: {e}")
        return False


def update_execution_trades(name: str, new_trades: List[Dict], new_portfolio_value: Dict = None) -> bool:
    """
    Append new trades to an existing execution.
    
    Args:
        name: Execution name
        new_trades: List of new trade dictionaries to append
        new_portfolio_value: Optional {date, value} to append to portfolio values
        
    Returns:
        True if updated successfully
    """
    execution = load_execution(name)
    if not execution:
        st.error(f"Execution '{name}' not found.")
        return False
    
    try:
        from huggingface_hub import upload_file
        
        token, repo = _get_hf_credentials()
        if not token or not repo:
            return False
        
        # Append new trades
        execution['trades'].extend(new_trades)
        
        # Append new portfolio value if provided
        if new_portfolio_value:
            execution['portfolio_values'].append(new_portfolio_value)
        
        # Update timestamp
        execution['last_updated'] = datetime.now().isoformat()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(execution, f, indent=2, default=str)
            tmp_path = f.name
        
        # Upload to HF
        upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=_get_execution_path(name),
            repo_id=repo,
            repo_type="dataset",
            token=token,
            commit_message=f"Update execution trades: {name}"
        )
        
        # Cleanup
        Path(tmp_path).unlink(missing_ok=True)
        
        # Clear cache
        list_executions.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error updating execution: {e}")
        return False


def load_execution(name: str) -> Optional[Dict]:
    """
    Load an execution from Hugging Face.
    
    Args:
        name: Execution name to load
        
    Returns:
        Execution data dictionary or None if not found
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError
    
    token, repo = _get_hf_credentials()
    if not token or not repo:
        return None
    
    try:
        file_path = hf_hub_download(
            repo_id=repo,
            filename=_get_execution_path(name),
            repo_type="dataset",
            token=token
        )
        
        with open(file_path, 'r') as f:
            execution_data = json.load(f)
        
        return execution_data
        
    except EntryNotFoundError:
        return None
    except Exception as e:
        st.error(f"Error loading execution: {e}")
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def list_executions() -> List[Dict]:
    """
    List all saved executions from Hugging Face.
    
    Returns:
        List of execution summaries (name, mode, created_at, template)
    """
    from huggingface_hub import list_repo_files
    
    token, repo = _get_hf_credentials()
    if not token or not repo:
        return []
    
    try:
        files = list_repo_files(
            repo_id=repo,
            repo_type="dataset",
            token=token
        )
        
        # Extract execution names from file paths
        executions = []
        for f in files:
            if f.startswith("executions/") and f.endswith(".json"):
                # Remove "executions/" and ".json"
                name = f[11:-5].replace("_", " ")
                
                # Try to load metadata
                execution_data = load_execution(name)
                if execution_data:
                    executions.append({
                        'name': name,
                        'mode': execution_data.get('mode', 'unknown'),
                        'strategy_template': execution_data.get('strategy_template', 'unknown'),
                        'created_at': execution_data.get('created_at', ''),
                        'last_updated': execution_data.get('last_updated', ''),
                        'capital': execution_data.get('capital', 0),
                        'trade_count': len(execution_data.get('trades', [])),
                        'notes': execution_data.get('notes', ''),
                        'tags': execution_data.get('tags', [])
                    })
        
        # Sort by last_updated descending
        executions.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
        
        return executions
        
    except Exception as e:
        print(f"Error listing executions: {e}")
        return []


def update_execution_notes(name: str, notes: str = None, tags: List[str] = None) -> bool:
    """Update notes and tags for an existing execution."""
    execution = load_execution(name)
    if not execution:
        st.error(f"Execution '{name}' not found.")
        return False
    
    try:
        from huggingface_hub import upload_file
        
        token, repo = _get_hf_credentials()
        if not token or not repo:
            return False
        
        if notes is not None:
            execution['notes'] = notes
        if tags is not None:
            execution['tags'] = tags
        
        execution['last_updated'] = datetime.now().isoformat()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(execution, f, indent=2, default=str)
            tmp_path = f.name
        
        upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=_get_execution_path(name),
            repo_id=repo,
            repo_type="dataset",
            token=token,
            commit_message=f"Update execution notes: {name}"
        )
        
        Path(tmp_path).unlink(missing_ok=True)
        list_executions.clear()
        return True
    except Exception as e:
        st.error(f"Error updating execution notes: {e}")
        return False


def delete_execution(name: str) -> bool:
    """
    Delete an execution from Hugging Face.
    
    Args:
        name: Execution name to delete
        
    Returns:
        True if deleted successfully
    """
    from huggingface_hub import HfApi
    
    token, repo = _get_hf_credentials()
    if not token or not repo:
        return False
    
    try:
        api = HfApi(token=token)
        api.delete_file(
            path_in_repo=_get_execution_path(name),
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Delete execution: {name}"
        )
        
        # Clear cache
        list_executions.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error deleting execution: {e}")
        return False
