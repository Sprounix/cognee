import asyncio

import cognee


async def clearn_all_data():
    # nest_asyncio.apply()
    print("Deleting all files and data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    print("All files deleted.")


if __name__ == "__main__":
    asyncio.run(
        clearn_all_data()
    )
