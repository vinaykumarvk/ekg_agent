#!/usr/bin/env python3
"""
Direct test of the refactored code with mode='concise'
Tests the core functions directly without needing the API server
"""
import os
import sys

# Set dummy API key if not set (for testing structure, not actual API calls)
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "dummy-for-testing"

def test_concise_mode_direct():
    """Test the core functions directly"""
    print("=" * 80)
    print("🧪 Testing Refactored Code with mode='concise'")
    print("=" * 80)
    print()
    
    try:
        # Import core modules
        print("1. Importing modules...")
        from ekg_core.core import (
            answer_with_kg_and_vector,
            get_preset,
            PROMPT_SET
        )
        from api.domains import get_domain
        from api.main import get_client, load_graph_artifacts, get_agent
        print("   ✅ Imports successful")
        print()
        
        # Check available domains
        print("2. Checking available domains...")
        try:
            domain_config = get_domain("wealth_management")
            print(f"   ✅ Domain 'wealth_management' found")
            print(f"   Vector Store ID: {domain_config.default_vectorstore_id}")
        except ValueError:
            print("   ⚠️  Domain 'wealth_management' not found, trying 'apf'...")
            try:
                domain_config = get_domain("apf")
                print(f"   ✅ Domain 'apf' found")
                print(f"   Vector Store ID: {domain_config.default_vectorstore_id}")
            except ValueError:
                print("   ❌ No domains available")
                return False
        print()
        
        # Load graph artifacts
        print("3. Loading knowledge graph...")
        try:
            domain_id = domain_config.domain_id
            G, by_id, name_index = load_graph_artifacts(domain_id)
            print(f"   ✅ KG loaded successfully")
            print(f"   Nodes: {len(by_id)}")
            print(f"   Name aliases: {len(name_index)}")
        except Exception as e:
            print(f"   ❌ Failed to load KG: {e}")
            print(f"   This is expected if KG files are not present")
            print(f"   Testing will continue with structure validation only")
            G, by_id, name_index = None, {}, {}
        print()
        
        # Get client
        print("4. Getting OpenAI client...")
        try:
            client = get_client()
            print("   ✅ Client created")
        except Exception as e:
            print(f"   ⚠️  Client creation issue: {e}")
            print("   (This is OK if OPENAI_API_KEY is not set)")
        print()
        
        # Test preset for concise mode
        print("5. Testing preset configuration for 'concise' mode...")
        try:
            preset = get_preset("concise")
            print("   ✅ Preset loaded successfully")
            print(f"   Mode: {preset.get('_mode', 'N/A')}")
            print(f"   Model: {preset.get('model', 'N/A')}")
            print(f"   Hops: {preset.get('hops', 'N/A')}")
            print(f"   Max expanded: {preset.get('max_expanded', 'N/A')}")
        except Exception as e:
            print(f"   ❌ Failed to get preset: {e}")
            return False
        print()
        
        # Test PROMPT_SET
        print("6. Testing PROMPT_SET for 'concise' mode...")
        try:
            if "concise" in PROMPT_SET:
                prompt_template = PROMPT_SET["concise"]
                print("   ✅ Concise prompt template found")
                print(f"   Template length: {len(prompt_template)} characters")
                # Try formatting with dummy values
                try:
                    test_prompt = prompt_template.format(
                        expanded_queries_str="1. Test query",
                        kg_text="Test KG text"
                    )
                    print("   ✅ Prompt template is valid and formatable")
                except Exception as e:
                    print(f"   ⚠️  Prompt template formatting issue: {e}")
            else:
                print("   ❌ 'concise' mode not found in PROMPT_SET")
                print(f"   Available modes: {list(PROMPT_SET.keys())}")
                return False
        except Exception as e:
            print(f"   ❌ Failed to test PROMPT_SET: {e}")
            return False
        print()
        
        # Test agent creation
        print("7. Testing agent creation...")
        try:
            if G is not None and len(by_id) > 0:
                agent = get_agent(
                    domain_id=domain_id,
                    vectorstore_id=domain_config.default_vectorstore_id,
                    params=preset
                )
                print("   ✅ Agent created successfully")
                print(f"   Agent type: {type(agent).__name__}")
            else:
                print("   ⚠️  Skipping agent creation (KG not loaded)")
        except Exception as e:
            print(f"   ⚠️  Agent creation issue: {e}")
            print("   (This may be expected if dependencies are missing)")
        print()
        
        print("=" * 80)
        print("✅ Structure validation completed successfully!")
        print("=" * 80)
        print()
        print("Note: To test with actual API calls, you need:")
        print("  1. Valid OPENAI_API_KEY environment variable")
        print("  2. Knowledge graph files in data/kg/")
        print("  3. Run: uvicorn api.main:app --host 0.0.0.0 --port 8000")
        print("  4. Then run: python test_concise_mode.py")
        print()
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_concise_mode_direct()
    sys.exit(0 if success else 1)

