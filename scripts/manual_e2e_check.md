# 수동 End-to-End 확인

전제: 서버가 `uvicorn main:app --port 8000`으로 떠 있고, `.env`에 유효한
`ANTHROPIC_API_KEY`와 로컬 MySQL 접속 정보가 채워져 있음. `sample.webm`은 직접
녹음한 3~5초 분량의 한국어 발화 파일로 교체할 것.

1. session_id 생성 (PowerShell):
   ```
   $sessionId = [guid]::NewGuid().ToString()
   echo $sessionId
   ```

2. 음성 분석:
   ```
   curl -X POST http://localhost:8000/api/v1/voice/analyze `
     -F "session_id=$sessionId" `
     -F "audio=@sample.webm;type=audio/webm"
   ```
   확인: `transcript`가 실제 발화 내용과 비슷한지, `emotions`에 9개 감정 키가
   있고 합이 대략 1에 가까운지.

3. 대화 응답 (2번 응답의 transcript/emotions를 그대로 넣기):
   ```
   curl -X POST http://localhost:8000/api/v1/chat/reply `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\", \"transcript\": \"<2번 transcript>\", \"emotions\": <2번 emotions>}"
   ```
   확인: `reply_text`가 '뭉이' 톤으로 자연스러운지.

4. TTS (3번 응답의 reply_text를 그대로 넣기):
   ```
   curl -X POST http://localhost:8000/api/v1/tts `
     -H "Content-Type: application/json" `
     -d "{\"text\": \"<3번 reply_text>\"}" `
     --output reply.wav
   ```
   확인: `reply.wav`를 재생했을 때 음성이 들리는지 (플레이스홀더 화자 목소리).

5. 2~4번을 2~3회 반복해서 여러 턴 쌓기.

6. 세션 종료:
   ```
   curl -X POST http://localhost:8000/api/v1/session/end `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\"}"
   ```
   확인: `dominant_emotion`과 `average_emotions`가 지금까지 턴들의 감정과
   대략 일치하는지.

7. 일기 생성:
   ```
   curl -X POST http://localhost:8000/api/v1/diary/generate `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\"}"
   ```
   확인: `diary_text`가 1인칭 일기 형식인지, `summary`가 한 줄인지, MySQL의
   `diaries` 테이블에 실제로 row가 생겼는지 (`SELECT * FROM diaries ORDER BY
   id DESC LIMIT 1;`).

8. 같은 session_id로 6번을 다시 호출 → `404` 확인 (diary/generate가 세션을
   정리했는지 검증).
