import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api/axios'
import {
    Users,
    FileText,
    BarChart3,
    Eye,
    Bell,
    ArrowRight,
    Clock,
    RefreshCw,
    AlertCircle
} from 'lucide-react'

function Dashboard() {
    const navigate = useNavigate()
    const [stats, setStats] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [isRefreshing, setIsRefreshing] = useState(false)
    const premierChargement = useRef(true)

    const chargerStats = useCallback(async () => {
        // Defer : évite d'appeler les setState de façon synchrone dans l'effet
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
        const interval = setInterval(chargerStats, 60000)
        return () => clearInterval(interval)
    }, [chargerStats])

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

            {/* Alerte escalades en attente */}
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

            {/* Cartes statistiques */}
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

            {/* Statistiques globales */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-gray-800 mb-4">Statistiques globales</h2>
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