/* ================================================================
   EK SE SRESHTHA - LOGIN PAGE SCRIPT
   ----------------------------------------------------------------
   Handles UI interactions: password toggle, form enhancement.
   Form submission is handled by Django server-side (traditional POST).
   ================================================================ */

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize password toggle
    initPasswordToggle();
    
    // Optional: Auto-focus email field
    const emailInput = document.getElementById('login-email');
    if (emailInput) {
        emailInput.focus();
    }
});

/* ================================================================
   PASSWORD VISIBILITY TOGGLE
   ----------------------------------------------------------------
   Flips the password field between hidden and visible so users can
   confirm what they typed.
   ================================================================ */

function initPasswordToggle() {
    const toggle = document.querySelector('.login-password-toggle');
    const input = document.getElementById('login-password');
    
    if (!toggle || !input) return;
    
    toggle.addEventListener('click', (e) => {
        e.preventDefault();
        togglePassword();
    });
}

// Global function for onclick handler
function togglePassword() {
    const input = document.getElementById('login-password');
    const toggle = document.querySelector('.login-password-toggle');
    if (!input || !toggle) return;
    
    if (input.type === 'password') {
        input.type = 'text';
        toggle.setAttribute('aria-label', 'Hide password');
    } else {
        input.type = 'password';
        toggle.setAttribute('aria-label', 'Show password');
    }
}

/* ================================================================
   FORM ENHANCEMENT (optional - for better UX)
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    const submitBtn = document.querySelector('.login-submit');
    
    if (!form || !submitBtn) return;
    
    // Add loading state on submit
    form.addEventListener('submit', () => {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Signing in...';
    });
    
    // Clear errors on input
    const inputs = form.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            const errorBox = document.getElementById('login-error');
            if (errorBox) {
                errorBox.hidden = true;
                errorBox.textContent = '';
            }
            // Clear field-specific errors
            const fieldError = input.closest('.form-group').querySelector('.form-error');
            if (fieldError) {
                fieldError.remove();
            }
            input.classList.remove('error');
        });
    });
});

/* ================================================================
   SPINNER STYLES (injected via JS for convenience)
   ================================================================ */

const style = document.createElement('style');
style.textContent = `
    .spinner {
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid rgba(255,255,255,0.3);
        border-radius: 50%;
        border-top-color: white;
        animation: spin 0.8s linear infinite;
        margin-right: 8px;
        vertical-align: middle;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
`;
document.head.appendChild(style);