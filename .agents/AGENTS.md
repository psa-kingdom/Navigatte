# Development & Git Operations Rules

## 1. Branch and Repository Protection
- **Target Branch**: Always develop and commit on the `test` branch.
- **Main Protection**: `main` is the protected production baseline and MUST NOT be modified, rebased, or pushed to directly.
- **Push Destination**: Ensure plain `git push` targets `origin/test`.

## 2. Git and GitHub Authentication
Whenever performing git push or other write operations to a GitHub remote repository, follow these guidelines:
1. Always check if there is a `GITHUB_TOKEN` defined in the global `.env` file (`c:\Users\srv93\.env`).
2. If `GITHUB_TOKEN` is present in the `.env` file, load and use it for authentication during git push or API operations to avoid hanging on headless credential manager prompts.
3. To push safely using the token without exposing it in logs or command execution history:
   - Extract the token dynamically in the terminal session (e.g., using PowerShell `$tokenLine = Get-Content "c:\Users\srv93\.env" | Where-Object { $_ -match "^GITHUB_TOKEN=" } | Select-Object -First 1; $token = $tokenLine.Split('=', 2)[1].Trim(); git push "https://x-access-token:$token@github.com/..."` or equivalent).
   - Do not print or leak the token in logs, error messages, or shell command outputs.

## 3. Architecture & Code Integrity
- Maintain separation of concerns: `frontend/` (React SPA) and `backend/` (FastAPI).
- Never commit `.env` or raw secret keys to Git.
- Maintain backward compatibility with existing MongoDB documents and API routes.
- Run backend pytest tests before committing code changes.
