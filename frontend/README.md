# LangTrader Frontend

AI-Powered Cryptocurrency Trading Dashboard built with Next.js.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui (Radix UI)
- **Data Fetching**: TanStack Query
- **State Management**: Zustand
- **Charts**: Recharts

## Features

- **Dashboard**: Overview of bots, performance metrics, PnL charts
- **Bot Management**: Start/stop bots, view status, positions, trades
- **Real-time Updates**: WebSocket integration for live data
- **Settings**: Configure exchanges, LLM providers, workflows

## Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Docker

```bash
# Build and run with Docker
docker build -t langtrader-frontend .
docker run -p 3000:3000 langtrader-frontend

# Or use Docker Compose from project root
docker compose up frontend
```

## Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_API_KEY=dev-key-123
```

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Dashboard
│   ├── bots/              # Bot management
│   ├── trades/            # Trade history
│   └── settings/          # Configuration pages
├── components/            # React components
│   ├── ui/               # shadcn/ui base components
│   ├── bots/             # Bot-specific components
│   ├── charts/           # Chart components
│   └── layout/           # Layout components
├── hooks/                 # Custom React hooks
├── lib/                   # Utilities and API clients
│   └── api/              # Backend API modules
├── stores/               # Zustand stores
└── types/                # TypeScript type definitions
```

## API Integration

The frontend connects to the LangTrader FastAPI backend:

- REST API: `http://localhost:8000/api/v1/`
- WebSocket: `ws://localhost:8000/ws/trading/{bot_id}`

All API calls require `X-API-Key` header authentication.

