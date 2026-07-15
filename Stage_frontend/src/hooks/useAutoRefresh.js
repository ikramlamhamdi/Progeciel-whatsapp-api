import { useEffect, useRef, useCallback } from 'react';

/**
 * Hook générique pour rafraîchir des données automatiquement à intervalle régulier.
 * @param {Function} callback - la fonction de fetch à appeler (idéalement mémorisée avec useCallback)
 * @param {number} intervalMs - intervalle en millisecondes (défaut: 10000 = 10s)
 * @param {Object} options - { pauseWhenHidden: bool }
 */
export function useAutoRefresh(callback, intervalMs = 10000, options = {}) {
    const { pauseWhenHidden = true } = options;
    const savedCallback = useRef(callback);
    const intervalRef = useRef(null);
    const isFetching = useRef(false); // protège contre les requêtes qui se chevauchent

    useEffect(() => {
        savedCallback.current = callback;
    }, [callback]);

    const runCallback = useCallback(async () => {
        if (isFetching.current) return; // une requête est déjà en cours, on skip ce cycle
        isFetching.current = true;
        try {
            await savedCallback.current();
        } catch (err) {
            console.error('Erreur dans useAutoRefresh:', err);
        } finally {
            isFetching.current = false;
        }
    }, []);

    const startInterval = useCallback(() => {
        if (intervalRef.current) return;
        intervalRef.current = setInterval(runCallback, intervalMs);
    }, [intervalMs, runCallback]);

    const stopInterval = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
    }, []);

    useEffect(() => {
        startInterval();

        if (pauseWhenHidden) {
            const handleVisibilityChange = () => {
                if (document.hidden) {
                    stopInterval();
                } else {
                    runCallback(); // refresh immédiat au retour sur l'onglet
                    startInterval();
                }
            };
            document.addEventListener('visibilitychange', handleVisibilityChange);
            return () => {
                stopInterval();
                document.removeEventListener('visibilitychange', handleVisibilityChange);
            };
        }

        return () => stopInterval();
    }, [startInterval, stopInterval, pauseWhenHidden, runCallback]);
}