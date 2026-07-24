import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api/axios'
import { useAutoRefresh } from '../hooks/useAutoRefresh'
import {
    Users,
    FileText,
    BarChart3,
    Eye,
    Bell,
    ArrowRight,
    Clock,
    RefreshCw,
    AlertCircle,
    Bot,
    Inbox,

} from 'lucide-react'

const STATUTS_MESSAGES = [
    { cle: 'nouveau', label: 'Nouveau', couleur: 'bg-blue-500', texte: 'text-blue-700', fond: 'bg-blue-50' },
    { cle: 'lu', label: 'Lu', couleur: 'bg-sky-400', texte: 'text-sky-700', fond: 'bg-sky-50' },
    { cle: 'en_traitement', label: 'En traitement', couleur: 'bg-amber-400', texte: 'text-amber-700', fond: 'bg-amber-50' },
    { cle: 'repondu_auto', label: 'Répondu (IA)', couleur: 'bg-emerald-500', texte: 'text-emerald-700', fond: 'bg-emerald-50' },
    { cle: 'repondu_manuel', label: 'Répondu (manuel)', couleur: 'bg-teal-500', texte: 'text-teal-700', fond: 'bg-teal-50' },
    { cle: 'escalade', label: 'Escaladé', couleur: 'bg-rose-500', texte: 'text-rose-700', fond: 'bg-rose-50' },
    { cle: 'echec', label: 'Échec technique', couleur: 'bg-gray-400', texte: 'text-gray-700', fond: 'bg-gray-50' },
]

function Dashboard() {
    const navigate = useNavigate()
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const premierChargement = useRef(true)

    const chargerStats = useCallback(async () => {
        await Promise.resolve()

        if (premierChargement.current) setLoading(true)
        setIsRefreshing(true)
        setError(null)
        try {
            const [resTemplates, resClients, resCampagnes, resMessages] = await Promise.all([
                api.get('/templates/'),
                api.get('/clients/'),
                api.get('/campagnes/'),
                api.get('/webhook/messages/').catch(() => ({ data: [] })),
            ])

            const campagnes = resCampagnes.data
            const messages = resMessages.data

            const totalEnvoyes = campagnes.reduce((acc, c) => acc + (c.statistiques?.envoye || 0), 0)
            const totalLus = campagnes.reduce((acc, c) => acc + (c.statistiques?.lu || 0), 0)
            const totalEchecs = campagnes.reduce((acc, c) => acc + (c.statistiques?.echec || 0), 0)
            const tauxOuverture = totalEnvoyes > 0 ? ((totalLus / totalEnvoyes) * 100).toFixed(1) : 0

            const escaladesActives = messages.filter(m => m.statut === 'escalade')

            // Répartition des messages entrants par statut
            const messagesParStatut = STATUTS_MESSAGES.reduce((acc, s) => {
                acc[s.cle] = messages.filter(m => m.statut === s.cle).length
                return acc
            }, {})

            // Taux d'automatisation : parmi les messages traités (auto ou manuel), part traitée par l'IA seule
            const totalTraites = messagesParStatut.repondu_auto + messagesParStatut.repondu_manuel
            const tauxAutomatisation = totalTraites > 0
                ? ((messagesParStatut.repondu_auto / totalTraites) * 100).toFixed(1)
                : null

            // Messages nécessitant encore une action (pas encore traités définitivement)
            const messagesEnAttente = messagesParStatut.nouveau + messagesParStatut.lu + messagesParStatut.en_traitement

            setStats({
                templates: resTemplates.data.length,
                templatesApprouves: resTemplates.data.filter(t => t.statut === 'approuve').length,
                clients: resClients.data.length,
                campagnes: campagnes.length,
                campagnesTerminees: campagnes.filter(c => c.statut === 'terminee').length,
                totalEnvoyes,
                totalLus,
                totalEchecs,
                tauxOuverture,
                derniersCampagnes: campagnes.slice(0, 5),
                totalMessages: messages.length,
                escaladesActives,
                messagesParStatut,
                tauxAutomatisation,
                messagesEnAttente,
            })
        } catch (err) {
            const erreur = err.response?.data?.erreur || 'Erreur lors du chargement du dashboard.'
            setError(erreur)
        } finally {
            setLoading(false)
            setIsRefreshing(false)
            premierChargement.current = false
        }
    }, [])

    useEffect(() => {
        chargerStats()
    }, [chargerStats])

    // Auto-refresh toutes les 15s (au lieu du setInterval manuel précédent à 60s)
    useAutoRefresh(chargerStats, 15000)

    const couleurStatut = (statut) => {
        const couleurs = {
            brouillon: 'bg-gray-100 text-gray-600',
            terminee: 'bg-emerald-100 text-emerald-700',
            partiel: 'bg-amber-100 text-amber-700',
            echec: 'bg-rose-100 text-rose-700',
            en_cours: 'bg-blue-100 text-blue-700',
        }
        return couleurs[statut] || 'bg-gray-100 text-gray-600'
    }

    if (loading) return (
        <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
            <span className="ml-2 text-gray-500 font-medium">Chargement des données...</span>
        </div>
    )

    if (error) return (
        <div className="flex flex-col items-center justify-center p-8 bg-red-50 rounded-xl border border-red-100">
            <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
            <p className="text-red-700 font-medium">{error}</p>
            <button onClick={chargerStats} className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                Réessayer
            </button>
        </div>
    )

    const totalMessagesPourBarre = stats.totalMessages || 0

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Tableau de bord</h1>
                    <p className="text-gray-500 mt-1">Aperçu en temps réel de vos activités.</p>
                </div>
                <button
                    onClick={chargerStats}
                    disabled={isRefreshing}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 hover:text-blue-600 transition-all shadow-sm disabled:opacity-50"
                >
                    <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                    {isRefreshing ? 'Mise à jour...' : 'Actualiser'}
                </button>
            </div>

            {stats.escaladesActives.length > 0 && (
                <div className="flex items-center justify-between p-4 bg-amber-50 border border-amber-200 rounded-xl">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-amber-200 rounded-full">
                            <Bell className="w-5 h-5 text-amber-700" />
                        </div>
                        <div>
                            <p className="font-semibold text-amber-900">
                                {stats.escaladesActives.length} message{stats.escaladesActives.length > 1 ? 's' : ''} escaladé{stats.escaladesActives.length > 1 ? 's' : ''}
                            </p>
                            <p className="text-sm text-amber-700">Nécessite une intervention manuelle.</p>
                        </div>
                    </div>
                    <button
                        onClick={() => navigate('/messages')}
                        className="flex items-center gap-1 text-sm font-bold text-amber-700 hover:underline"
                    >
                        Gérer <ArrowRight className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Cartes principales */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                    titre="Templates"
                    valeur={stats.templates}
                    detail={`${stats.templatesApprouves} approuvés`}
                    icon={<FileText className="text-blue-600" />}
                    color="bg-blue-50"
                    onClick={() => navigate('/templates')}
                />
                <StatCard
                    titre="Clients"
                    valeur={stats.clients}
                    detail="Total abonnés"
                    icon={<Users className="text-purple-600" />}
                    color="bg-purple-50"
                    onClick={() => navigate('/clients')}
                />
                <StatCard
                    titre="Campagnes"
                    valeur={stats.campagnes}
                    detail={`${stats.campagnesTerminees} terminées`}
                    icon={<BarChart3 className="text-amber-600" />}
                    color="bg-amber-50"
                    onClick={() => navigate('/campagnes')}
                />
                <StatCard
                    titre="Taux d'ouverture"
                    valeur={`${stats.tauxOuverture}%`}
                    detail={`${stats.totalLus} messages lus`}
                    icon={<Eye className="text-emerald-600" />}
                    color="bg-emerald-50"
                    onClick={() => navigate('/campagnes')}
                />
            </div>

            {/* Stats campagnes (envoi) */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Statistiques d'envoi (campagnes)</h2>
                <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                        <p className="text-3xl font-bold text-blue-600">{stats.totalEnvoyes.toLocaleString()}</p>
                        <p className="text-sm text-gray-500 mt-1">Envoyés</p>
                    </div>
                    <div className="text-center">
                        <p className="text-3xl font-bold text-emerald-600">{stats.totalLus.toLocaleString()}</p>
                        <p className="text-sm text-gray-500 mt-1">Lus</p>
                    </div>
                    <div className="text-center">
                        <p className="text-3xl font-bold text-rose-500">{stats.totalEchecs.toLocaleString()}</p>
                        <p className="text-sm text-gray-500 mt-1">Échecs</p>
                    </div>
                </div>
            </div>

            {/* Stats messages entrants */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-gray-800">Messages entrants</h2>
                    <Link
                        to="/messages"
                        className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
                    >
                        Voir tout <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-4 border border-gray-100">
                        <div className="p-2 bg-gray-200 rounded-lg">
                            <Inbox className="w-5 h-5 text-gray-600" />
                        </div>
                        <div>
                            <p className="text-xl font-bold text-gray-800">{stats.totalMessages}</p>
                            <p className="text-xs text-gray-500">Total reçus</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 bg-emerald-50 rounded-lg p-4 border border-emerald-100">
                        <div className="p-2 bg-emerald-200 rounded-lg">
                            <Bot className="w-5 h-5 text-emerald-700" />
                        </div>
                        <div>
                            <p className="text-xl font-bold text-emerald-700">
                                {stats.tauxAutomatisation !== null ? `${stats.tauxAutomatisation}%` : '—'}
                            </p>
                            <p className="text-xs text-gray-500">Taux d'automatisation IA</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 bg-amber-50 rounded-lg p-4 border border-amber-100">
                        <div className="p-2 bg-amber-200 rounded-lg">
                            <Clock className="w-5 h-5 text-amber-700" />
                        </div>
                        <div>
                            <p className="text-xl font-bold text-amber-700">{stats.messagesEnAttente}</p>
                            <p className="text-xs text-gray-500">En attente de traitement</p>
                        </div>
                    </div>
                </div>

                {/* Barre de répartition visuelle */}
                {totalMessagesPourBarre > 0 && (
                    <div className="mb-5">
                        <div className="flex w-full h-3 rounded-full overflow-hidden bg-gray-100">
                            {STATUTS_MESSAGES.map((s) => {
                                const count = stats.messagesParStatut[s.cle] || 0
                                const pourcentage = (count / totalMessagesPourBarre) * 100
                                if (pourcentage === 0) return null
                                return (
                                    <div
                                        key={s.cle}
                                        className={s.couleur}
                                        style={{ width: `${pourcentage}%` }}
                                        title={`${s.label} : ${count}`}
                                    />
                                )
                            })}
                        </div>
                    </div>
                )}

                {/* Compteurs détaillés par statut */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                    {STATUTS_MESSAGES.map((s) => (
                        <div key={s.cle} className={`rounded-lg p-3 border border-gray-100 ${s.fond}`}>
                            <div className="flex items-center gap-1.5 mb-1">
                                <span className={`w-2 h-2 rounded-full ${s.couleur}`} />
                                <span className={`text-xs font-medium ${s.texte}`}>{s.label}</span>
                            </div>
                            <p className={`text-lg font-bold ${s.texte}`}>
                                {stats.messagesParStatut[s.cle] || 0}
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Dernières campagnes */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
                <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
                    <h2 className="text-lg font-semibold text-gray-800">Dernières campagnes</h2>
                    <Link
                        to="/campagnes"
                        className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1"
                    >
                        Voir tout <ArrowRight className="w-4 h-4" />
                    </Link>
                </div>
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                        <th className="text-left px-5 py-3 text-gray-600 font-medium">Nom</th>
                        <th className="text-left px-5 py-3 text-gray-600 font-medium">Template</th>
                        <th className="text-left px-5 py-3 text-gray-600 font-medium">Statut</th>
                        <th className="text-right px-5 py-3 text-gray-600 font-medium">Envoyés</th>
                        <th className="text-right px-5 py-3 text-gray-600 font-medium">Lus</th>
                        <th className="text-right px-5 py-3 text-gray-600 font-medium">Échecs</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                    {stats.derniersCampagnes.length === 0 ? (
                        <tr>
                            <td colSpan="6" className="px-6 py-12 text-center">
                                <div className="flex flex-col items-center">
                                    <Clock className="w-10 h-10 text-gray-300 mb-2" />
                                    <p className="text-gray-500 italic">Aucune campagne n'a encore été lancée.</p>
                                    <button onClick={() => navigate('/campagnes')} className="mt-2 text-blue-600 font-medium hover:underline">
                                        Créer votre première campagne
                                    </button>
                                </div>
                            </td>
                        </tr>
                    ) : stats.derniersCampagnes.map((c) => (
                        <tr
                            key={c.id}
                            className="hover:bg-gray-50 transition-colors cursor-pointer"
                            onClick={() => navigate('/campagnes')}
                        >
                            <td className="px-5 py-4 font-semibold text-gray-800">{c.nom}</td>
                            <td className="px-5 py-3 text-gray-500">{c.template_nom || '—'}</td>
                            <td className="px-5 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${couleurStatut(c.statut)}`}>
                    {c.statut}
                  </span>
                            </td>
                            <td className="px-5 py-3 text-blue-600 font-medium text-right">{c.statistiques?.envoye || 0}</td>
                            <td className="px-5 py-3 text-emerald-600 font-medium text-right">{c.statistiques?.lu || 0}</td>
                            <td className="px-5 py-3 text-rose-500 font-medium text-right">{c.statistiques?.echec || 0}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function StatCard({ titre, valeur, detail, icon, color, onClick }) {
    return (
        <div
            onClick={onClick}
            className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer group"
        >
            <div className="flex justify-between items-start">
                <div>
                    <p className="text-sm font-medium text-gray-500">{titre}</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{valeur}</p>
                    <p className="text-xs text-gray-400 mt-1">{detail}</p>
                </div>
                <div className={`p-2 rounded-lg ${color}`}>
                    {icon}
                </div>
            </div>
        </div>
    )
}

export default Dashboard