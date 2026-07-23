/* ================================================================
   EK SE SRESHTHA - LOGIN PAGE SCRIPT
   ----------------------------------------------------------------
   Handles the sign-in form: validation, credential check, and
   redirect to the dashboard on success.

   In production, this would POST to an auth API. Here it looks
   up credentials in the seeded Super Admin list stored in
   localStorage.
   ================================================================ */

/* ================================================================
   INITIALIZATION
   ----------------------------------------------------------------
   When the page loads, if a session already exists, skip login
   and go straight to the dashboard.
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    const existingSession = localStorage.getItem('ess_session');
    if (existingSession) {
        window.location.href = 'pages/dashboard.html';
        return;
    }

    // Hook up the form submit handler
    const form = document.getElementById('login-form');
    form.addEventListener('submit', handleLogin);
});

/* ================================================================
   PASSWORD VISIBILITY TOGGLE
   ----------------------------------------------------------------
   Flips the password field between hidden and visible so users can
   confirm what they typed.
   ================================================================ */

function togglePassword() {
    const input = document.getElementById('login-password');
    const toggle = document.querySelector('.login-password-toggle');
    if (input.type === 'password') {
        input.type = 'text';
        toggle.setAttribute('aria-label', 'Hide password');
    } else {
        input.type = 'password';
        toggle.setAttribute('aria-label', 'Show password');
    }
}

/* ================================================================
   FORM SUBMISSION HANDLER
   ----------------------------------------------------------------
   Validates inputs, checks credentials, creates a session,
   and redirects on success.
   ================================================================ */

function handleLogin(event) {
    // Prevent the default form POST that would reload the page
    event.preventDefault();

    // Get form values
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('login-remember').checked;
    const errorBox = document.getElementById('login-error');

    // Reset any previous error
    errorBox.hidden = true;
    errorBox.textContent = '';

    // ------------------------------------------------------------
    // Basic client-side validation
    // ------------------------------------------------------------
    if (!email || !password) {
        showLoginError('Please enter both email and password.');
        return;
    }

    if (!isValidEmail(email)) {
        showLoginError('Please enter a valid email address.');
        return;
    }

    // ------------------------------------------------------------
    // Verify credentials against the stored Super Admin records.
    // In a real app, this would be an HTTPS request to your API.
    // ------------------------------------------------------------
    const admins = getRecords('superAdmins');
    const admin = admins.find(a =>
        a.email.toLowerCase() === email.toLowerCase() && a.password === password
    );

    if (!admin) {
        showLoginError('Invalid email or password. Try the demo credentials shown below.');
        return;
    }

    // ------------------------------------------------------------
    // Success - create the session and redirect
    // ------------------------------------------------------------
    const session = {
        id: admin.id,
        name: admin.name,
        email: admin.email,
        role: admin.role || 'super_admin',
        loggedInAt: new Date().toISOString(),
        remember: remember
    };
    localStorage.setItem('ess_session', JSON.stringify(session));

    // Give the user a quick success signal, then redirect
    showToast('Signed in successfully', 'success', 1500);
    setTimeout(() => {
        window.location.href = 'pages/dashboard.html';
    }, 600);
}

/* ================================================================
   HELPERS
   ================================================================ */

/**
 * Shows an inline error box above the submit button.
 */
function showLoginError(message) {
    const errorBox = document.getElementById('login-error');
    errorBox.textContent = message;
    errorBox.hidden = false;
    // Briefly focus for screen reader announcement
    errorBox.setAttribute('role', 'alert');
}

/**
 * Simple email regex - accepts standard email formats.
 */
function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
