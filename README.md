# Deep Vision by DNS

Plataforma de videoanalitica profesional para CCTV con NVIDIA DeepStream, Motion Gate inteligente y Vision Assistant (LLM local).

## Arquitectura

```
┌─────────────┐  RTSP   ┌──────────────┐  GPU   ┌──────────────┐
│  NVR/Camaras├────────►│ Motion Gate  ├───────►│  DeepStream  │
│    ONVIF    │         │   (CPU)      │        │  YOLO + Track│
└─────────────┘         └──────────────┘        └──────┬───────┘
                                                       │
                              ┌─────────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │  Redis PubSub    │
                    │  Event Stream    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │  PostgreSQL  │ │  MinIO   │ │   FastAPI     │
     │  Events/DB   │ │ Snapshots│ │   Backend     │
     └──────────────┘ │  Clips   │ └──────┬───────┘
                      └──────────┘        │
                                          ▼
                                 ┌──────────────┐
                                 │  Next.js 14  │
                                 │  Dashboard   │
                                 │  (dark-only) │
                                 └──────────────┘
                                          │
                                 ┌──────────────┐
                                 │   Ollama +   │
                                 │   Phi-3 Mini │
                                 │  (Assistant) │
                                 └──────────────┘
```

## Quick Start

```bash
cp .env.example .env
# Edita .env con tus valores

docker compose up -d

# Frontend: http://localhost:3000
# API:      http://localhost:8000
# MinIO:    http://localhost:9001
# Assistant:http://localhost:8001
```

Login: `admin` / `admin123`

## Tech Stack

- **Video/IA**: NVIDIA DeepStream 7.1 + YOLO (TensorRT FP16)
- **Backend**: FastAPI + PostgreSQL 16 + Redis 7
- **Frontend**: Next.js 14 + Tailwind + shadcn/ui (dark-only)
- **Storage**: MinIO (S3) para snapshots y clips
- **Assistant**: Ollama + Phi-3 Mini 3.8B (Text-to-SQL local)
- **Deploy**: Docker Compose
