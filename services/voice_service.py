import asyncio

from fastapi.concurrency import run_in_threadpool

from services import pitch_service, ser_service, stt_service


async def analyze_voice(app_state, wav_path: str) -> tuple[str, dict[str, float], float, float]:
    async def run_stt():
        async with app_state.stt_lock:
            return await run_in_threadpool(stt_service.transcribe, app_state.stt_model, wav_path)

    async def run_ser():
        async with app_state.ser_lock:
            return await run_in_threadpool(ser_service.analyze_emotion, app_state.ser_model, wav_path)

    async def run_pitch():
        return await run_in_threadpool(pitch_service.analyze_pitch, wav_path)

    transcript, emotions, (pitch_mean, pitch_std) = await asyncio.gather(run_stt(), run_ser(), run_pitch())
    return transcript, emotions, pitch_mean, pitch_std
