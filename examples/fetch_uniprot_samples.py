import asyncio
from pathlib import Path
from protein_annotation_toolkit.clients import UniProtClient

async def fetch_samples():
    uniprot_ids = ["P13773", "P29274", "P41595", "Q02293", "Q63357"]
    output_dir = Path("examples/data/uniprot_xml")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with UniProtClient() as client:
        for uid in uniprot_ids:
            try:
                print(f"Fetching {uid}...")
                xml = await client.fetch_xml(uid)
                output_file = output_dir / f"{uid}.xml"
                output_file.write_text(xml)
                print(f"Saved {uid} to {output_file}")
            except Exception as e:
                print(f"Failed to fetch {uid}: {e}")

asyncio.run(fetch_samples())
