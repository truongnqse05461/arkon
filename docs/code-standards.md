# Code Standards & Coding Conventions

This document outlines the coding standards, patterns, and conventions used across the Arkon codebase.

---

## 🐍 Backend (Python / FastAPI)

The backend uses Python 3.11+ and FastAPI.

### 1. Import Styling
* **Absolute Imports:** All internal module imports must start with the absolute path prefix `app.` (e.g., `from app.config import settings`).
* **Circular Dependency Prevention:** To avoid import loops, import database models, schemas, and service functions locally inside functions or routes rather than at the top of the file. See [main.py](file:///d:/workspace/src/truongnqse05461/arkon/app/main.py) for examples.
* **Imports Order:** Group imports by standard library, third-party libraries (e.g., FastAPI, SQLAlchemy), and internal modules, separated by blank lines.

### 2. Async/Await & Database Sessions
* All database communications are asynchronous using SQLAlchemy's `AsyncSession`.
* **Isolated Transactions:** The background workers and parallel tasks must run on their own session lifecycle to avoid session conflicts (`IllegalStateChangeError`). Each parallel chunk writer in the MRP pipeline opens its own session context.
* Critical operations that modify pages are secured with advisory locks at the database layer (e.g., locking by page slug hash). See [wiki_service.py](file:///d:/workspace/src/truongnqse05461/arkon/app/services/wiki_service.py).

### 3. Logging & Error Handling
* Use `loguru` for logging rather than standard `logging`.
  ```python
  from loguru import logger
  logger.info("Informational message")
  logger.success("Operation succeeded")
  logger.warning("Potential issue detected")
  logger.error("Error occurred")
  ```
* REST routes must catch expected errors and return appropriate HTTP status codes (e.g., `403 Forbidden` for out-of-scope requests or `404 Not Found`).
* Worker scripts must handle exceptions gracefully to prevent database connections from leaking or jobs hanging in a perpetual `running` state.

---

## ⚛️ Frontend (React / TypeScript / Next.js)

The frontend uses Next.js 16 (App Router), React 19, Tailwind CSS v4, and TypeScript.

### 1. Component Structure & Path Aliases
* **Aliases:** Use `@/` as a path alias pointing to the root of `frontend/src/` (e.g., `import { Button } from "@/components/ui/button"`).
* **Client Directives:** Any component that makes use of state hooks (`useState`, `useEffect`), callbacks, or browser-specific events must explicitly declare `"use client";` at the very first line of the file. See [page.tsx](file:///d:/workspace/src/truongnqse05461/arkon/frontend/src/app/(portal)/audit/page.tsx).

### 2. Styling & Layout
* **Tailwind v4:** Styling is performed utility-first using Tailwind CSS classes. Avoid inline style elements.
* **Component Primitives:** Rely on Shadcn-derived primitives located in `frontend/src/components/ui/` for buttons, cards, tables, and dialogs.
* **Icons:** Use Google's **Material Symbols Outlined** for icons.
  ```tsx
  <span className="material-symbols-outlined text-base">refresh</span>
  ```

### 3. State Management & Data Fetching
* Use the absolute `api` wrapper in `frontend/src/lib/api.ts` for handling requests to the backend. It wraps fetch calls, resolves errors, and enforces types.
* Standardize callback dependencies using `useCallback` to prevent unnecessary component re-renders.
* **Keyboards & Accessibility:** Keyboard shortcuts (e.g. in the review console) must check if the target element is an input or textarea to avoid firing shortcuts while the user is typing feedback notes.
