#!/usr/bin/env python3
"""
Golden File Generator
Creates reference outputs for all 6 MCP tools to establish baseline behavior.
These files will be used for regression testing during refactoring.
"""

import asyncio
import importlib.util
import json
from pathlib import Path

# Import the server module
spec = importlib.util.spec_from_file_location(
    "finos_server", "finos-ai-governance-mcp-server.py"
)
finos_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finos_server)


class GoldenFileGenerator:
    """Generate golden files for all MCP tools"""

    def __init__(self):
        self.golden_dir = Path("tests/golden")
        self.golden_dir.mkdir(parents=True, exist_ok=True)

    async def capture_search_mitigations(self):
        """Capture search_mitigations tool outputs"""
        print("📄 Capturing search_mitigations outputs...")

        # Test queries with different patterns
        test_queries = [
            "data",
            "security",
            "model",
            "encryption",
            "access control",
            "nonexistent_term_12345",  # Should return empty results
        ]

        results = {}

        for query in test_queries:
            try:
                # Simulate what the MCP tool would do
                all_docs = []

                # Get all mitigation documents
                for filename in finos_server.MITIGATION_FILES:
                    doc = await finos_server.get_document_content(
                        "mitigation", filename
                    )
                    if doc:
                        all_docs.append(doc)

                # Simple search - check if query appears in title or content
                matches = []
                for doc in all_docs:
                    title = doc.get("metadata", {}).get("title", "")
                    content = doc.get("content", "")

                    if (
                        query.lower() in title.lower()
                        or query.lower() in content.lower()
                    ):
                        matches.append(
                            {
                                "id": doc["filename"].split("_")[0],
                                "title": title,
                                "filename": doc["filename"],
                                "snippet": (
                                    content[:200] + "..."
                                    if len(content) > 200
                                    else content
                                ),
                                "url": doc["url"],
                            }
                        )

                results[query] = {
                    "query": query,
                    "results": matches,
                    "count": len(matches),
                }

                print(f"  ✅ Query '{query}': {len(matches)} matches")

            except Exception as e:
                print(f"  ❌ Query '{query}' failed: {e}")
                results[query] = {"error": str(e)}

        # Save golden file
        golden_file = self.golden_dir / "search_mitigations.json"
        with open(golden_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"  💾 Saved to {golden_file}")
        return results

    async def capture_search_risks(self):
        """Capture search_risks tool outputs"""
        print("📄 Capturing search_risks outputs...")

        test_queries = [
            "data",
            "model",
            "injection",
            "privacy",
            "nonexistent_term_12345",
        ]

        results = {}

        for query in test_queries:
            try:
                all_docs = []

                # Get all risk documents
                for filename in finos_server.RISK_FILES:
                    doc = await finos_server.get_document_content("risk", filename)
                    if doc:
                        all_docs.append(doc)

                # Simple search
                matches = []
                for doc in all_docs:
                    title = doc.get("metadata", {}).get("title", "")
                    content = doc.get("content", "")

                    if (
                        query.lower() in title.lower()
                        or query.lower() in content.lower()
                    ):
                        matches.append(
                            {
                                "id": doc["filename"].split("_")[0],
                                "title": title,
                                "filename": doc["filename"],
                                "snippet": (
                                    content[:200] + "..."
                                    if len(content) > 200
                                    else content
                                ),
                                "url": doc["url"],
                            }
                        )

                results[query] = {
                    "query": query,
                    "results": matches,
                    "count": len(matches),
                }

                print(f"  ✅ Query '{query}': {len(matches)} matches")

            except Exception as e:
                print(f"  ❌ Query '{query}' failed: {e}")
                results[query] = {"error": str(e)}

        golden_file = self.golden_dir / "search_risks.json"
        with open(golden_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"  💾 Saved to {golden_file}")
        return results

    async def capture_get_mitigation_details(self):
        """Capture get_mitigation_details outputs"""
        print("📄 Capturing get_mitigation_details outputs...")

        # Test with first few mitigations and an invalid one
        test_ids = ["mi-1", "mi-2", "mi-17", "mi-999"]  # Include invalid ID
        results = {}

        for mitigation_id in test_ids:
            try:
                # Find matching filename
                filename = None
                for f in finos_server.MITIGATION_FILES:
                    if f.startswith(f"{mitigation_id}_"):
                        filename = f
                        break

                if not filename:
                    results[mitigation_id] = {
                        "error": f"Mitigation {mitigation_id} not found"
                    }
                    print(f"  ❌ {mitigation_id}: not found")
                    continue

                doc = await finos_server.get_document_content("mitigation", filename)
                if doc:
                    # Extract key information for golden file
                    results[mitigation_id] = {
                        "id": mitigation_id,
                        "title": doc["metadata"].get("title", ""),
                        "sequence": doc["metadata"].get("sequence"),
                        "doc_status": doc["metadata"].get("doc-status"),
                        "type": doc["metadata"].get("type"),
                        "content_length": len(doc["content"]),
                        "metadata_fields": list(doc["metadata"].keys()),
                        "filename": doc["filename"],
                        "url": doc["url"],
                    }
                    print(
                        f"  ✅ {mitigation_id}: {doc['metadata'].get('title', 'No title')}"
                    )
                else:
                    results[mitigation_id] = {"error": "Failed to fetch document"}
                    print(f"  ❌ {mitigation_id}: fetch failed")

            except Exception as e:
                results[mitigation_id] = {"error": str(e)}
                print(f"  ❌ {mitigation_id}: {e}")

        golden_file = self.golden_dir / "get_mitigation_details.json"
        with open(golden_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"  💾 Saved to {golden_file}")
        return results

    async def capture_get_risk_details(self):
        """Capture get_risk_details outputs"""
        print("📄 Capturing get_risk_details outputs...")

        test_ids = ["ri-1", "ri-2", "ri-10", "ri-999"]  # Include invalid ID
        results = {}

        for risk_id in test_ids:
            try:
                filename = None
                for f in finos_server.RISK_FILES:
                    if f.startswith(f"{risk_id}_"):
                        filename = f
                        break

                if not filename:
                    results[risk_id] = {"error": f"Risk {risk_id} not found"}
                    print(f"  ❌ {risk_id}: not found")
                    continue

                doc = await finos_server.get_document_content("risk", filename)
                if doc:
                    results[risk_id] = {
                        "id": risk_id,
                        "title": doc["metadata"].get("title", ""),
                        "sequence": doc["metadata"].get("sequence"),
                        "doc_status": doc["metadata"].get("doc-status"),
                        "content_length": len(doc["content"]),
                        "metadata_fields": list(doc["metadata"].keys()),
                        "filename": doc["filename"],
                        "url": doc["url"],
                    }
                    print(f"  ✅ {risk_id}: {doc['metadata'].get('title', 'No title')}")
                else:
                    results[risk_id] = {"error": "Failed to fetch document"}
                    print(f"  ❌ {risk_id}: fetch failed")

            except Exception as e:
                results[risk_id] = {"error": str(e)}
                print(f"  ❌ {risk_id}: {e}")

        golden_file = self.golden_dir / "get_risk_details.json"
        with open(golden_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"  💾 Saved to {golden_file}")
        return results

    async def capture_list_all_mitigations(self):
        """Capture list_all_mitigations output"""
        print("📄 Capturing list_all_mitigations output...")

        try:
            mitigations = []

            for filename in finos_server.MITIGATION_FILES:
                doc = await finos_server.get_document_content("mitigation", filename)
                if doc:
                    mitigations.append(
                        {
                            "id": doc["filename"].split("_")[0],
                            "title": doc["metadata"].get("title", ""),
                            "sequence": doc["metadata"].get("sequence"),
                            "doc_status": doc["metadata"].get("doc-status"),
                            "filename": doc["filename"],
                        }
                    )

            # Sort by sequence
            mitigations.sort(key=lambda x: x.get("sequence", 999))

            result = {"mitigations": mitigations, "count": len(mitigations)}

            golden_file = self.golden_dir / "list_all_mitigations.json"
            with open(golden_file, "w") as f:
                json.dump(result, f, indent=2)

            print(f"  ✅ Listed {len(mitigations)} mitigations")
            print(f"  💾 Saved to {golden_file}")
            return result

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            return {"error": str(e)}

    async def capture_list_all_risks(self):
        """Capture list_all_risks output"""
        print("📄 Capturing list_all_risks output...")

        try:
            risks = []

            for filename in finos_server.RISK_FILES:
                doc = await finos_server.get_document_content("risk", filename)
                if doc:
                    risks.append(
                        {
                            "id": doc["filename"].split("_")[0],
                            "title": doc["metadata"].get("title", ""),
                            "sequence": doc["metadata"].get("sequence"),
                            "doc_status": doc["metadata"].get("doc-status"),
                            "filename": doc["filename"],
                        }
                    )

            # Sort by sequence
            risks.sort(key=lambda x: x.get("sequence", 999))

            result = {"risks": risks, "count": len(risks)}

            golden_file = self.golden_dir / "list_all_risks.json"
            with open(golden_file, "w") as f:
                json.dump(result, f, indent=2)

            print(f"  ✅ Listed {len(risks)} risks")
            print(f"  💾 Saved to {golden_file}")
            return result

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            return {"error": str(e)}

    async def generate_all_golden_files(self):
        """Generate all golden files"""
        print("🏗️  Generating Golden Files for All 6 MCP Tools...")
        print("=" * 60)

        generators = [
            self.capture_search_mitigations,
            self.capture_search_risks,
            self.capture_get_mitigation_details,
            self.capture_get_risk_details,
            self.capture_list_all_mitigations,
            self.capture_list_all_risks,
        ]

        results = {}

        for generator in generators:
            try:
                tool_name = generator.__name__.replace("capture_", "")
                results[tool_name] = await generator()
            except Exception as e:
                print(f"❌ {generator.__name__} failed: {e}")
                results[generator.__name__] = {"error": str(e)}

        print("=" * 60)
        print("🎉 Golden file generation complete!")
        print(f"📁 Files saved in: {self.golden_dir}")

        return results


async def main():
    """Main golden file generator"""
    generator = GoldenFileGenerator()
    await generator.generate_all_golden_files()
    print("\n✅ GOLDEN FILES READY FOR REGRESSION TESTING")


if __name__ == "__main__":
    asyncio.run(main())
