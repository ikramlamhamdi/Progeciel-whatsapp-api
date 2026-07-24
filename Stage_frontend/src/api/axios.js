import axios from 'axios'

// Lit un cookie par son nom (utilisé pour récupérer le token CSRF de Django)
function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
    return match ? decodeURIComponent(match[2]) : null
}

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
    headers: {
        'Content-Type': 'application/json',
    },
    withCredentials: true, // envoie les cookies (session + csrf) avec chaque requête
})

// Ajoute automatiquement le header CSRF sur les requêtes qui modifient des données
api.interceptors.request.use((config) => {
    const methodesProtegees = ['post', 'put', 'patch', 'delete']
    if (methodesProtegees.includes(config.method)) {
        const csrfToken = getCookie('csrftoken')
        if (csrfToken) {
            config.headers['X-CSRFToken'] = csrfToken
        }
    }
    return config
})

export default api