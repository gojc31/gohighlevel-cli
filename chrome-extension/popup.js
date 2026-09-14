let refreshToken = null;

const grabBtn = document.getElementById("grabBtn");
const copyBtn = document.getElementById("copyBtn");
const status = document.getElementById("status");
const preview = document.getElementById("preview");

function setStatus(msg, type) {
  status.textContent = msg;
  status.className = type;
}

// Grab the refresh token from GHL's IndexedDB
grabBtn.addEventListener("click", async () => {
  grabBtn.disabled = true;
  setStatus("Reading IndexedDB...", "info");

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab?.url?.match(/gohighlevel\.com|leadconnectorhq\.com/)) {
      setStatus("Navigate to a GHL page first (app.gohighlevel.com)", "error");
      grabBtn.disabled = false;
      return;
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractToken,
      world: "MAIN",
    });

    const result = results?.[0]?.result;

    if (result?.refreshToken) {
      refreshToken = result.refreshToken;
      setStatus("Token grabbed successfully!", "success");
      preview.textContent = refreshToken.substring(0, 40) + "..." + refreshToken.substring(refreshToken.length - 20);
      preview.style.display = "block";
      copyBtn.disabled = false;
    } else if (result?.error) {
      setStatus("Error: " + result.error, "error");
    } else {
      setStatus("No token found. Make sure you're logged into GHL.", "error");
    }
  } catch (err) {
    setStatus("Error: " + err.message, "error");
  }

  grabBtn.disabled = false;
});

// Copy to clipboard
copyBtn.addEventListener("click", async () => {
  if (!refreshToken) return;

  try {
    await navigator.clipboard.writeText(refreshToken);
    setStatus("Copied! Paste into .env as GHL_FIREBASE_REFRESH_TOKEN=<token>", "success");
  } catch {
    // Fallback
    const ta = document.createElement("textarea");
    ta.value = refreshToken;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    setStatus("Copied! Paste into .env as GHL_FIREBASE_REFRESH_TOKEN=<token>", "success");
  }
});

// This function runs in the PAGE context (not extension context)
function extractToken() {
  return new Promise((resolve) => {
    try {
      const request = indexedDB.open("firebaseLocalStorageDb");

      request.onerror = () => resolve({ error: "Cannot open IndexedDB" });

      request.onsuccess = (event) => {
        const db = event.target.result;

        if (!db.objectStoreNames.contains("firebaseLocalStorage")) {
          resolve({ error: "firebaseLocalStorage store not found" });
          return;
        }

        const tx = db.transaction("firebaseLocalStorage", "readonly");
        const store = tx.objectStore("firebaseLocalStorage");
        const getAll = store.getAll();

        getAll.onsuccess = () => {
          const entries = getAll.result;
          for (const entry of entries) {
            const val = entry?.value || entry;
            const stm = val?.stsTokenManager;
            if (stm?.refreshToken) {
              resolve({
                refreshToken: stm.refreshToken,
                accessToken: stm.accessToken,
                expirationTime: stm.expirationTime,
                uid: val.uid,
              });
              return;
            }
          }
          resolve({ error: "No stsTokenManager.refreshToken found in entries" });
        };

        getAll.onerror = () => resolve({ error: "Failed to read store" });
      };
    } catch (err) {
      resolve({ error: err.message });
    }
  });
}
