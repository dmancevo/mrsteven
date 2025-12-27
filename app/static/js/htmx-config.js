/**
 * HTMX configuration and event handlers
 */

// Configure HTMX and event handlers when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('HTMX config loading...');

    // Set default timeout for requests
    htmx.config.timeout = 10000; // 10 seconds

    // Configure WebSocket reconnection
    htmx.config.wsReconnectDelay = 'full-jitter';

    console.log('HTMX configured successfully');

    // Global HTMX event handlers
    document.body.addEventListener('htmx:configRequest', function(event) {
        // Add any custom headers here if needed
        // event.detail.headers['X-Custom-Header'] = 'value';
    });

    document.body.addEventListener('htmx:beforeSwap', function(event) {
        // Handle error responses
        if (event.detail.xhr.status === 404) {
            console.error('Resource not found');
            event.detail.shouldSwap = false;
            showToast('Error: Resource not found', 'error');
        } else if (event.detail.xhr.status === 400) {
            console.error('Bad request:', event.detail.xhr.responseText);
            event.detail.shouldSwap = false;
            try {
                const response = JSON.parse(event.detail.xhr.responseText);
                showToast(response.detail || 'Invalid request', 'error');
            } catch (e) {
                showToast('Invalid request', 'error');
            }
        } else if (event.detail.xhr.status >= 500) {
            console.error('Server error');
            event.detail.shouldSwap = false;
            showToast('Server error. Please try again.', 'error');
        }
    });

    document.body.addEventListener('htmx:beforeRequest', function(event) {
        console.log('HTMX request starting:', event.detail.pathInfo.requestPath);
    });

    document.body.addEventListener('htmx:afterRequest', function(event) {
        console.log('HTMX request complete:', {
            path: event.detail.pathInfo.requestPath,
            status: event.detail.xhr.status,
            headers: {
                'HX-Redirect': event.detail.xhr.getResponseHeader('HX-Redirect')
            }
        });

        // Log successful requests in development
        if (event.detail.successful) {
            console.log('Request successful');
        }
    });
});

// Toast notification helper
function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} fixed top-4 right-4 w-auto max-w-md shadow-lg z-50 animate-fade-in`;
    toast.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('animate-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes fade-in {
        from { opacity: 0; transform: translateY(-1rem); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes fade-out {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(-1rem); }
    }

    .animate-fade-in {
        animation: fade-in 0.3s ease-out;
    }

    .animate-fade-out {
        animation: fade-out 0.3s ease-out;
    }
`;
document.head.appendChild(style);

// Make showToast globally available
window.showToast = showToast;
