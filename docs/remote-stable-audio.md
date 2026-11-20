# Use a remote Stable Audio 3 API

Remiqora can keep its UI, backend, track database, and generated audio on your
computer while forwarding Stable Audio 3 requests to a remote instance of
Remiqora's `external/sa3-server`.

1. Start `sa3-server` on the remote machine and make port `8002` reachable over
   HTTPS. The server must listen on `0.0.0.0`, and its `/health` and `/v1/...`
   endpoints must use the same API as this repository.
2. Copy `backend/.env.example` to `backend/.env` if necessary.
3. Add the remote API base URL:

   ```ini
   STABLE_AUDIO_API_URL=https://your-pod-8002.proxy.runpod.net
   ```

   Do not include a trailing slash or `/health`.
4. The RunPod HTTP proxy is public. Protect a permanently exposed server by
   setting `STABLE_AUDIO_API_TOKEN` on the remote Pod and the matching local value:

   ```ini
   STABLE_AUDIO_API_TOKEN=replace-with-a-random-secret
   ```

5. Start Remiqora with `dev.bat` and open `http://localhost:5173`.

When `STABLE_AUDIO_API_URL` is set, Remiqora checks the remote `/health`
endpoint and does not launch or require a local `sa3-server` environment.
Stable Audio generation, polling, cancellation, reference-audio uploads, and
generated-file downloads continue through the local `/api/sa3/...` proxy.

Leaving `STABLE_AUDIO_API_URL` unset preserves the normal local Stable Audio
setup. Local checkpoint download APIs remain tied to a local Stable Audio
environment in remote mode, and the editor's optional CPU sample server still
requires a local Stable Audio installation.

## RunPod setup

The simplest deployment is a long-running NVIDIA GPU Pod. Use a RunPod
PyTorch image with Python 3.12 and CUDA 12.8, such as
`runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`. Attach a network volume at
`/workspace` with at least 30 GB; 50 GB leaves room for the environment,
multiple checkpoints, and generated output. A volume is pinned to its data
center, so deploy the Pod in that data center.

Expose `8002/http`. The RunPod proxy URL will be
`https://POD_ID-8002.proxy.runpod.net`.

In the Pod/template configuration, expose `22/tcp` only if you want SSH
access. The browser-based Web Terminal does not need port 22.

Set these Pod environment variables:

```ini
HF_HOME=/workspace/huggingface
SA3_OUT_DIR=/workspace/sa3-output
PYTHONUNBUFFERED=1
```

Optional variables:

```ini
# Required only for gated Stable Audio checkpoints.
HF_TOKEN=hf_your_read_token

# Recommended when 8002/http is publicly exposed.
STABLE_AUDIO_API_TOKEN=replace-with-a-random-secret
```

Prefer RunPod Secrets for `HF_TOKEN` and `STABLE_AUDIO_API_TOKEN` instead of
putting their values directly in a reusable template.

In the Pod terminal:

```bash
export HF_HOME=/workspace/huggingface
export SA3_OUT_DIR=/workspace/sa3-output

cd /workspace
git clone https://github.com/YOUR_GITHUB_USER/remiqora.git
cd remiqora/external/sa3-server

python -m pip install --break-system-packages uv
uv sync
```

The `export` commands are unnecessary when the values were already added in
the Pod configuration, but are shown so the same steps work in an ad-hoc shell.

If `git clone` reports `Could not resolve host: github.com`, wait briefly and
retry first. If DNS is still unavailable, check and temporarily replace the
Pod's DNS configuration:

```bash
cat /etc/resolv.conf
printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf
getent hosts github.com
git clone https://github.com/YOUR_GITHUB_USER/remiqora.git
```

RunPod may recreate `/etc/resolv.conf` after a Pod restart.

Download at least one checkpoint. The base checkpoints are open:

```bash
.venv/bin/python -m sa3_server.download small-music-base
```

For a gated checkpoint, accept its Hugging Face license first and provide a
token with Read access:

```bash
export HF_TOKEN=hf_your_read_token
.venv/bin/python -m sa3_server.download medium
```

Optionally protect the public RunPod HTTP proxy with the same token that local
Remiqora will send:

```bash
export STABLE_AUDIO_API_TOKEN=replace-with-a-random-secret
```

Setting this token after the server has started does not change the running
process; restart `sa3-server` after changing it.

Start the API:

```bash
nohup .venv/bin/python -m sa3_server \
  --host 0.0.0.0 \
  --port 8002 \
  --preload small-music-base \
  --out-dir /workspace/sa3-output \
  > /workspace/sa3-server.log 2>&1 &
```

Use `--preload medium` instead if that is the checkpoint you downloaded. Then
verify it from the Pod and your computer:

```bash
curl http://127.0.0.1:8002/health
curl https://POD_ID-8002.proxy.runpod.net/health
curl https://POD_ID-8002.proxy.runpod.net/v1/models
```

When `STABLE_AUDIO_API_TOKEN` is set on RunPod, include the header in manual
checks:

```bash
curl -H 'Authorization: Bearer replace-with-a-random-secret' \
  https://POD_ID-8002.proxy.runpod.net/health
```

Keep checkpoints, code, output, and the virtual environment under
`/workspace`; the container disk is temporary and does not survive a Pod
restart.
