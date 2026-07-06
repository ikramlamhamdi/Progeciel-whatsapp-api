import { useEffect, useState, useCallback, useMemo } from 'react'
import api from '../api/axios'
import {
    RefreshCw,
    Plus,
    X,
    Upload,
    Search,
    Inbox,
    Users,
} from 'lucide-react'

const FORM_INITIAL = {
    nom: '',
    numero: '',
    email: '',
    ville: '',
    entreprise: '',
    segment: 'prospect',
}

const FILTRES_INITIAL = {
    recherche: '',
    segment: 'tous',
}

const couleurSegment = (segment) => {
    const couleurs = {
        prospect: 'bg-gray-100 text-gray-600 border-gray-200',
        actif: 'bg-blue-100 text-blue-600 border-blue-200',
        inactif: 'bg-orange-100 text-orange-600 border-orange-200',
        vip: 'bg-purple-100 text-purple-700 border-purple-200',
    }
    return couleurs[segment] || 'bg-gray-100 text-gray-600 border-gray-200'
}

function Clients() {
    const [clients, setClients] = useState([])
    const [loading, setLoading] = useState(true)
    const [showForm, setShowForm] = useState(false)
    const [message, setMessage] = useState(null)
    const [fichierExcel, setFichierExcel] = useState(null)
    const [filtres, setFiltres] = useState(FILTRES_INITIAL)

    const [form, setForm] = useState(FORM_INITIAL)

    const chargerClients = useCallback(async () => {
        await Promise.resolve()
        setLoading(true)
        try {
            const res = await api.get('/clients/')
            setClients(res.data)
        } catch (err) {
            setMessage({ type: 'error', text: 'Erreur lors du chargement des clients.' })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        chargerClients()
    }, [chargerClients])

    const handleChange = (e) => {
        setForm({ ...form, [e.target.name]: e.target.value })
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            await api.post('/clients/', form)
            setMessage({ type: 'success', text: 'Client ajouté avec succès !' })
            setShowForm(false)
            setForm(FORM_INITIAL)
            await chargerClients()
        } catch (err) {
            const erreur = err.response?.data?.numero?.[0] || err.response?.data?.erreur || 'Erreur lors de l\'ajout.'
            setMessage({ type: 'error', text: erreur })
        }
    }

    const handleImport = async () => {
        if (!fichierExcel) {
            setMessage({ type: 'error', text: 'Sélectionnez un fichier Excel.' })
            return
        }
        const formData = new FormData()
        formData.append('fichier', fichierExcel)
        try {
            const res = await api.post('/clients/import/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            setMessage({
                type: 'success',
                text: `Import terminé : ${res.data.clients_ajoutes} ajoutés, ${res.data.doublons_ignores_fichier} doublons dans le fichier, ${res.data.doublons_ignores_deja_en_base} déjà en base, ${res.data.numeros_invalides} numéros invalides.`
            })
            setFichierExcel(null)
            await chargerClients()
        } catch (err) {
            const erreur = err.response?.data?.erreur || 'Erreur lors de l\'import.'
            setMessage({ type: 'error', text: erreur })
        }
    }

    const segmentsDisponibles = useMemo(
        () => [...new Set(clients.map((c) => c.segment))].sort(),
        [clients]
    )

    const clientsFiltres = useMemo(() => {
        const recherche = filtres.recherche.trim().toLowerCase()
        return clients.filter((c) => {
            if (recherche) {
                const cible = `${c.nom} ${c.numero} ${c.email || ''} ${c.ville || ''} ${c.entreprise || ''}`.toLowerCase()
                if (!cible.includes(recherche)) return false
            }
            if (filtres.segment !== 'tous' && c.segment !== filtres.segment) return false
            return true
        })
    }, [clients, filtres])

    const filtresActifs = filtres.recherche !== '' || filtres.segment !== 'tous'

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Clients</h1>
                    <p className="text-gray-500 text-sm mt-1">Gérez votre base de contacts WhatsApp</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={chargerClients}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Rafraîchir
                    </button>
                    <button
                        onClick={() => setShowForm(!showForm)}
                        className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition-colors"
                    >
                        {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                        {showForm ? 'Annuler' : 'Nouveau client'}
                    </button>
                </div>
            </div>

            {/* Message feedback */}
            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
                    message.type === 'success'
                        ? 'bg-green-50 text-green-700 border border-green-200'
                        : 'bg-red-50 text-red-700 border border-red-200'
                }`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="ml-3 text-xs underline">Fermer</button>
                </div>
            )}

            {/* Import Excel */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm flex items-center gap-4">
                <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700 mb-1">Importer depuis Excel</p>
                    <p className="text-xs text-gray-400">Format : A=Nom, B=Numéro, C=Email, D=Ville, E=Entreprise, F=Segment</p>
                </div>
                <input
                    type="file"
                    accept=".xlsx"
                    onChange={(e) => setFichierExcel(e.target.files[0])}
                    className="text-sm text-gray-600"
                />
                <button
                    onClick={handleImport}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors shrink-0"
                >
                    <Upload className="w-4 h-4" /> Importer
                </button>
            </div>

            {/* Formulaire ajout manuel */}
            {showForm && (
                <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-gray-800 mb-4">Nouveau client</h2>
                    <form onSubmit={handleSubmit} className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
                            <input
                                name="nom"
                                value={form.nom}
                                onChange={handleChange}
                                placeholder="ex: Ikram Lamhaoui"
                                required
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Numéro WhatsApp</label>
                            <input
                                name="numero"
                                value={form.numero}
                                onChange={handleChange}
                                placeholder="ex: 212661234567"
                                required
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Email (optionnel)</label>
                            <input
                                name="email"
                                value={form.email}
                                onChange={handleChange}
                                placeholder="ex: ikram@email.com"
                                type="email"
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Ville</label>
                            <input
                                name="ville"
                                value={form.ville}
                                onChange={handleChange}
                                placeholder="ex: Casablanca"
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Entreprise</label>
                            <input
                                name="entreprise"
                                value={form.entreprise}
                                onChange={handleChange}
                                placeholder="ex: Progiciel System"
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Segment</label>
                            <select
                                name="segment"
                                value={form.segment}
                                onChange={handleChange}
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            >
                                <option value="prospect">Prospect</option>
                                <option value="actif">Actif</option>
                                <option value="inactif">Inactif</option>
                                <option value="vip">VIP</option>
                            </select>
                        </div>
                        <div className="col-span-3 flex justify-end">
                            <button
                                type="submit"
                                className="px-6 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition-colors"
                            >
                                Ajouter le client
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Filtres */}
            {!loading && clients.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm flex flex-col md:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            value={filtres.recherche}
                            onChange={(e) => setFiltres({ ...filtres, recherche: e.target.value })}
                            placeholder="Rechercher par nom, numéro, email, ville..."
                            className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                        />
                    </div>
                    <select
                        value={filtres.segment}
                        onChange={(e) => setFiltres({ ...filtres, segment: e.target.value })}
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                    >
                        <option value="tous">Tous les segments</option>
                        {segmentsDisponibles.map((s) => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                            {clientsFiltres.length} / {clients.length}
                        </span>
                        {filtresActifs && (
                            <button
                                onClick={() => setFiltres(FILTRES_INITIAL)}
                                className="text-xs text-gray-500 hover:text-gray-700 underline whitespace-nowrap"
                            >
                                Réinitialiser
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Liste clients */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 text-green-500 animate-spin mb-4" />
                    <p className="text-gray-500 font-medium">Chargement des clients...</p>
                </div>
            ) : clients.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Users className="w-12 h-12 text-gray-300 mb-4" />
                    <p className="text-gray-500 font-medium mb-2">Aucun client trouvé</p>
                    <p className="text-gray-400 text-sm">Ajoutez un client ou importez un fichier Excel</p>
                </div>
            ) : clientsFiltres.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Inbox className="w-12 h-12 text-gray-300 mb-4" />
                    <p className="text-gray-500 font-medium mb-2">Aucun résultat pour ces filtres</p>
                    <button
                        onClick={() => setFiltres(FILTRES_INITIAL)}
                        className="text-green-600 text-sm font-medium hover:underline mt-1"
                    >
                        Réinitialiser les filtres
                    </button>
                </div>
            ) : (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Nom</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Numéro</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Email</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Ville</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Entreprise</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Segment</th>
                            <th className="text-left px-4 py-3 text-gray-600 font-medium">Date d'ajout</th>
                        </tr>
                        </thead>
                        <tbody>
                        {clientsFiltres.map((c, i) => (
                            <tr key={c.id} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                <td className="px-4 py-3 font-medium text-gray-800">{c.nom}</td>
                                <td className="px-4 py-3 text-gray-600">{c.numero}</td>
                                <td className="px-4 py-3 text-gray-500">{c.email || '—'}</td>
                                <td className="px-4 py-3 text-gray-500">{c.ville || '—'}</td>
                                <td className="px-4 py-3 text-gray-500">{c.entreprise || '—'}</td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs px-2 py-1 rounded-full font-medium border ${couleurSegment(c.segment)}`}>
                                        {c.segment}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-gray-400">
                                    {new Date(c.date_ajout).toLocaleDateString('fr-FR')}
                                </td>
                            </tr>
                        ))}
                        </tbody>
                    </table>
                    <div className="px-4 py-3 border-t border-gray-100 text-xs text-gray-400">
                        {clientsFiltres.length} client{clientsFiltres.length > 1 ? 's' : ''}
                        {filtresActifs ? ` sur ${clients.length} au total` : ' au total'}
                    </div>
                </div>
            )}
        </div>
    )
}

export default Clients