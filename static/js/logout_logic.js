
// ======================================
// AUTO-LOGOUT ON EXIT (SECURITY)
// ======================================
window.addEventListener('beforeunload', function () {
    // User requested automatic logout on forced exit (tab close)
    console.log('🔒 Secure Exit: Clearing session data...');

    // 1. Clear active session flags
    sessionStorage.removeItem('k1_authenticated');
    sessionStorage.removeItem('k1_api_token');

    // 2. Clear Admin Token to force re-auth next time (Security)
    localStorage.removeItem('k1_admin_token');

    // 3. Notify backend of disconnect (Best effort)
    try {
        const userId = localStorage.getItem('k1_user_id');
        if (userId) {
            const data = JSON.stringify({ userId: userId, event: 'forced_logout' });
            navigator.sendBeacon('/api/logout-beacon', data);
        }
    } catch (e) {
        // Ignore errors on exit
    }
});
