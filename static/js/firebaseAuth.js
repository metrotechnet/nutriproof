// === Firebase Configuration ===
// TODO: Replace with your Firebase project config
const firebaseConfig = {
  apiKey: "AIzaSyAt84PdROclkyKffND6q5bAH3xvsx5r9RA",
  authDomain: "imx-nutriproof.firebaseapp.com",
  projectId: "imx-nutriproof",
  storageBucket: "imx-nutriproof.firebasestorage.app",
  messagingSenderId: "201727461753",
  appId: "1:201727461753:web:e347f73f403d874c2e87a8",
  measurementId: "G-CSMWL58692"
};
// === Firebase SDK (compat mode via CDN) ===
let _firebaseReady;
const firebaseReady = new Promise((resolve) => { _firebaseReady = resolve; });

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}

(async function initFirebase() {
    await loadScript("https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js");
    await loadScript("https://www.gstatic.com/firebasejs/10.12.0/firebase-auth-compat.js");
    firebase.initializeApp(firebaseConfig);
    _firebaseReady();
})();

// === Auth Helper Functions ===
async function loginWithEmail(email, password) {
    await firebaseReady;
    return firebase.auth().signInWithEmailAndPassword(email, password);
}

async function sendPasswordReset(email) {
    await firebaseReady;
    return firebase.auth().sendPasswordResetEmail(email);
}

async function logout() {
    await firebaseReady;
    return firebase.auth().signOut();
}

async function getCurrentUser() {
    await firebaseReady;
    return new Promise((resolve) => {
        firebase.auth().onAuthStateChanged(resolve);
    });
}

async function getIdToken() {
    await firebaseReady;
    const user = await getCurrentUser();
    if (user) return user.getIdToken();
    return null;
}

// === Authenticated Fetch ===
// Wraps fetch() to automatically include the Firebase ID token
async function authFetch(url, options = {}) {
    const token = await getIdToken();
    if (!token) {
        window.location.href = "/login";
        throw new Error("Not authenticated");
    }
    options.headers = options.headers || {};
    options.headers["Authorization"] = `Bearer ${token}`;
    return fetch(url, options);
}

// === Auth Guard ===
// Redirects to /login if not authenticated (for protected pages)
async function requireAuth() {
    const user = await getCurrentUser();
    if (!user) {
        window.location.href = "/login";
        return null;
    }
    return user;
}

// === Login Page UI Logic ===
document.addEventListener("DOMContentLoaded", () => {
    const loginSection = document.getElementById("login-section");
    const resetSection = document.getElementById("reset-section");
    if (!loginSection) return; // Not on login page

    // Toggle password visibility
    const toggleBtn = document.getElementById("toggle-password");
    const passwordInput = document.getElementById("login-password");
    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            const isPassword = passwordInput.type === "password";
            passwordInput.type = isPassword ? "text" : "password";
            toggleBtn.querySelector("i").className = isPassword ? "bi bi-eye-slash" : "bi bi-eye";
        });
    }

    // Show reset form
    document.getElementById("show-reset").addEventListener("click", (e) => {
        e.preventDefault();
        loginSection.style.display = "none";
        resetSection.style.display = "block";
    });

    // Show login form
    document.getElementById("show-login").addEventListener("click", (e) => {
        e.preventDefault();
        resetSection.style.display = "none";
        loginSection.style.display = "block";
    });

    // Login
    document.getElementById("btn-login").addEventListener("click", async () => {
        const email = document.getElementById("login-email").value.trim();
        const password = document.getElementById("login-password").value;
        const errorDiv = document.getElementById("login-error");
        errorDiv.classList.add("d-none");

        if (!email || !password) {
            errorDiv.textContent = "Veuillez remplir tous les champs.";
            errorDiv.classList.remove("d-none");
            return;
        }

        try {
            await loginWithEmail(email, password);
            window.location.href = "/main";
        } catch (err) {
            let msg = "Erreur de connexion.";
            if (err.code === "auth/user-not-found" || err.code === "auth/wrong-password" || err.code === "auth/invalid-credential") {
                msg = "Courriel ou mot de passe incorrect.";
            } else if (err.code === "auth/too-many-requests") {
                msg = "Trop de tentatives. Réessayez plus tard.";
            }
            errorDiv.textContent = msg;
            errorDiv.classList.remove("d-none");
        }
    });

    // Allow Enter key to login
    document.getElementById("login-password").addEventListener("keydown", (e) => {
        if (e.key === "Enter") document.getElementById("btn-login").click();
    });
    document.getElementById("login-email").addEventListener("keydown", (e) => {
        if (e.key === "Enter") document.getElementById("login-password").focus();
    });

    // Password Reset
    document.getElementById("btn-reset-password").addEventListener("click", async () => {
        const email = document.getElementById("reset-email").value.trim();
        const msgDiv = document.getElementById("reset-message");
        msgDiv.classList.add("d-none");

        if (!email) {
            msgDiv.className = "alert alert-danger";
            msgDiv.textContent = "Veuillez entrer votre courriel.";
            msgDiv.classList.remove("d-none");
            return;
        }

        try {
            await sendPasswordReset(email);
            msgDiv.className = "alert alert-success";
            msgDiv.textContent = "Un courriel de réinitialisation a été envoyé.";
            msgDiv.classList.remove("d-none");
        } catch (err) {
            let msg = "Erreur lors de l'envoi.";
            if (err.code === "auth/user-not-found") {
                msg = "Aucun compte trouvé avec ce courriel.";
            }
            msgDiv.className = "alert alert-danger";
            msgDiv.textContent = msg;
            msgDiv.classList.remove("d-none");
        }
    });

    // If already logged in, redirect to home
    getCurrentUser().then(user => {
        if (user) window.location.href = "/main";
    });
});
