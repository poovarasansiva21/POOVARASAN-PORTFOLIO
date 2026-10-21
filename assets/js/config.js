/* Runtime configuration. Safe to commit: contains no secrets.
   apiBase "" means the FastAPI app serves this site (same origin).
            Use e.g. https://portfolio-api.example.com when the site is on static hosting.
            The assistant and contact form show a clear "unavailable" state if the API can't be reached. */
window.PF_CONFIG = {
  apiBase: "",
  githubCacheMs: 15 * 60 * 1000
};
