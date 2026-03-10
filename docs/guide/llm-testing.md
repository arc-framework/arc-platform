# LLM Testing

Verify the reasoning and voice services with `curl` after running `arc run --profile think` (for reasoner only) or `arc run --profile ultra-instinct` (for voice + reasoner). Confirm all services are healthy before proceeding:

```bash
make dev-health
```

## Reasoner API — port 8802

The reasoner service (`arc-reasoner`) exposes an OpenAI-compatible REST API at `http://localhost:8802`.

### 1. Sync Chat Completions

A standard blocking request that returns the full response once generation is complete.

```bash
curl -X POST http://localhost:8802/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

Example response:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1741564800,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 16,
    "completion_tokens": 9,
    "total_tokens": 25
  }
}
```

### 2. Streaming Chat

Server-Sent Events (SSE) stream — tokens arrive as they are generated. Use `-N` to disable curl buffering.

```bash
curl -N -X POST http://localhost:8802/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Count from 1 to 5."}
    ],
    "stream": true
  }'
```

Example response (truncated SSE stream):

```
data: {"id":"chatcmpl-abc456","object":"chat.completion.chunk","created":1741564801,"model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"id":"chatcmpl-abc456","object":"chat.completion.chunk","created":1741564801,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc456","object":"chat.completion.chunk","created":1741564801,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":", 2"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc456","object":"chat.completion.chunk","created":1741564802,"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 3. Model List

Returns the models available from the configured LLM provider.

```bash
curl http://localhost:8802/models
```

Example response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4o",
      "object": "model",
      "created": 1741564800,
      "owned_by": "openai"
    },
    {
      "id": "gpt-4o-mini",
      "object": "model",
      "created": 1741564800,
      "owned_by": "openai"
    }
  ]
}
```

The model list reflects `LLM_PROVIDER` and `LLM_MODEL` environment variables set in your workspace. To use a different provider, set `LLM_PROVIDER=anthropic` or `LLM_PROVIDER=ollama` and restart the reasoner service.

## Voice Service API — port 8803

The voice service (`arc-voice-agent`) requires the `voice` capability. Start it with:

```bash
arc run --profile ultra-instinct
# or selectively:
arc run --profile think --capabilities voice
```

### 4. STT — Speech-to-Text Transcription

Transcribe an audio file using the Whisper model. Send the audio as a multipart form upload.

```bash
curl -X POST http://localhost:8803/v1/audio/transcriptions \
  -H "Accept: application/json" \
  -F "file=@/path/to/audio.wav;type=audio/wav" \
  -F "model=whisper-1" \
  -F "language=en"
```

The `file` field accepts `.wav`, `.mp3`, `.m4a`, `.ogg`, and `.flac`. The `language` field is optional — omit it to use automatic language detection.

Example response:

```json
{
  "text": "Hello, this is a test transcription.",
  "language": "en",
  "duration": 2.45
}
```

To record a short test clip on macOS:

```bash
# Record 5 seconds to test.wav
sox -d -r 16000 -c 1 test.wav trim 0 5
curl -X POST http://localhost:8803/v1/audio/transcriptions \
  -F "file=@test.wav;type=audio/wav" \
  -F "model=whisper-1"
```

### 5. TTS — Text-to-Speech Synthesis

Generate speech audio from text using the Piper TTS engine. Returns a WAV audio file.

```bash
curl -X POST http://localhost:8803/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Accept: audio/wav" \
  -d '{"model":"tts-1","input":"Hello world","voice":"alloy"}' \
  --output speech.wav
```

The response body is raw WAV audio. Pipe it directly to your audio player:

```bash
curl -s -X POST http://localhost:8803/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"The platform is running.","voice":"alloy"}' \
  | ffplay -nodisp -autoexit -f wav - 2>/dev/null
```

Supported `voice` values: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`. These map to Piper voice model files bundled with the service image.

Example response headers:

```
HTTP/1.1 200 OK
Content-Type: audio/wav
Content-Disposition: attachment; filename="speech.wav"
X-Duration-Secs: 1.23
```

## Health Checks

Both services expose a `/health` endpoint for liveness probes:

```bash
curl http://localhost:8802/health   # reasoner
curl http://localhost:8803/health   # voice
```

Both return `{"status": "ok"}` when the service is ready.
