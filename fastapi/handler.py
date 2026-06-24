import runpod
import os
import sys
import asyncio
import nest_asyncio

nest_asyncio.apply()

def handler(job):
    sys.path.insert(0, "/workspace/ImgGenScript")
    sys.path.insert(0, "/workspace/ImgGenScript/backend")
    
    from backend.src.batch.orchestrator import BatchOrchestrator
    
    job_input = job["input"]
    vrepro_id = job_input.get("vreproID", "")
    generation_type = job_input.get("generation_type", "fullbody")
    max_cycles = job_input.get("max_cycles", 1)
    
    try:
        async def main():
            orchestrator = BatchOrchestrator(generation_type=generation_type)
            await orchestrator.run(
                max_cycles=max_cycles,
                donor_list=[vrepro_id],
                use_pose_override=False,
                use_hands_refiner_override=True,
                use_amateur_effect_override=False,
            )
        
        asyncio.get_event_loop().run_until_complete(main())
        return {"status": "done", "vreproID": vrepro_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

runpod.serverless.start({"handler": handler})