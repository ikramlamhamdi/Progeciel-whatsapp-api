import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import api from '../api/axios'
import {
    Plus,
    X,
    Search,
    FileText,
    Send,
    CheckCircle,
    XCircle,
    Image as ImageIcon,
    Inbox,
    RefreshCw,
} from 'lucide-react'

const CHAMPS_CLIENT = [
    { value: 'client.nom', label: 'Nom du client' },
    { value: 'client.numero', label: 'Numéro' },
    { value: 'client.email', label: 'Email' },
    { value: 'client.ville', label: 'Ville' },
    { value: 'client.entreprise', label: 'Entreprise' },
    { value: 'client.segment', label: 'Segment' },
]

const FILTRES_INITIAL = {
    recherche: '',
    statut: 'tous',
}

const FILTRES_CLIENTS_INITIAL = {
    recherche: '',
    ville: 'tous',
    entreprise: 'tous',
    segment: 'tous',
}

const couleurStatut = (statut) => {
    const couleurs = {
        brouillon: 'bg-gray-100 text-gray-600 border-gray-200',
        programmee: 'bg-blue-100 text-blue-600 border-blue-200',
        en_cours: 'bg-yellow-100 text-yellow-600 border-yellow-200',
        terminee: 'bg-green-100 text-green-700 border-green-200',
        partiel: 'bg-orange-100 text-orange-600 border-orange-200',
        echec: 'bg-red-100 text-red-600 border-red-200',
    }
    return couleurs[statut] || 'bg-gray-100 text-gray-600 border-gray-200'
}

const couleurEnvoi = (statut) => {
    const couleurs = {
        envoye: 'text-blue-600',
        lu: 'text-green-600',
        echec: 'text-red-500',
        en_attente: 'text-gray-400',
    }
    return couleurs[statut] || 'text-gray-400'
}

function Campagnes() {
    const [campagnes, setCampagnes] = useState([])
    const [templates, setTemplates] = useState([])
    const [clients, setClients] = useState([])
    const [loading, setLoading] = useState(true)
    const [showForm, setShowForm] = useState(false)
    const [showDetail, setShowDetail] = useState(null)
    const [detail, setDetail] = useState(null)
    const [message, setMessage] = useState(null)
    const [envoyant, setEnvoyant] = useState(null)
    const [filtresClients, setFiltresClients] = useState(FILTRES_CLIENTS_INITIAL)
    const [filtres, setFiltres] = useState(FILTRES_INITIAL)

    const [headerFiles, setHeaderFiles] = useState({})
    const [headerMediaIds, setHeaderMediaIds] = useState({})
    const [uploadingMedia, setUploadingMedia] = useState(null)
    const [mappingVariables, setMappingVariables] = useState({})

    const [form, setForm] = useState({
        nom: '',
        template: '',
        client_ids: [],
    })

    const intervalsActifs = useRef({})

    const chargerDonnees = useCallback(async () => {
        await Promise.resolve()
        setLoading(true)
        try {
            const [resCampagnes, resTemplates, resClients] = await Promise.all([
                api.get('/campagnes/'),
                api.get('/templates/utilisables/'),
                api.get('/clients/'),
            ])
            setCampagnes(resCampagnes.data)
            setTemplates(resTemplates.data)
            setClients(resClients.data)
        } catch (err) {
            setMessage({ type: 'error', text: 'Erreur lors du chargement des données.' })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        chargerDonnees()
    }, [chargerDonnees])

    useEffect(() => {
        const intervalsAuMontage = intervalsActifs.current
        return () => {
            Object.values(intervalsAuMontage).forEach(clearInterval)
        }
    }, [])

    const handleChange = (e) => {
        setForm({ ...form, [e.target.name]: e.target.value })
    }

    const uploaderMediaHeader = async (campagneId) => {
        const fichier = headerFiles[campagneId]
        if (!fichier) return null

        const formData = new FormData()
        formData.append('fichier', fichier)

        setUploadingMedia(campagneId)
        try {
            const res = await api.post('/upload-media-envoi/', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            })
            const mediaId = res.data.media_id
            setHeaderMediaIds(prev => ({ ...prev, [campagneId]: mediaId }))
            return mediaId
        } catch (err) {
            const erreur = err.response?.data?.erreur || 'Erreur lors de l\'upload du média.'
            setMessage({ type: 'error', text: erreur })
            return null
        } finally {
            setUploadingMedia(null)
        }
    }

    // Valeurs uniques disponibles pour les selects, calculées à partir des clients réels
    const villesDisponibles = useMemo(
        () => [...new Set(clients.map(c => c.ville).filter(Boolean))].sort(),
        [clients]
    )
    const entreprisesDisponibles = useMemo(
        () => [...new Set(clients.map(c => c.entreprise).filter(Boolean))].sort(),
        [clients]
    )
    const segmentsDisponibles = useMemo(
        () => [...new Set(clients.map(c => c.segment).filter(Boolean))].sort(),
        [clients]
    )

    // Liste filtrée, recalculée automatiquement à chaque changement de filtre ou de clients
    const clientsFiltres = useMemo(() => {
        const recherche = filtresClients.recherche.trim().toLowerCase()
        return clients.filter(c => {
            if (recherche) {
                const matchNom = c.nom?.toLowerCase().includes(recherche)
                const matchNumero = c.numero?.includes(recherche)
                const matchEmail = c.email?.toLowerCase().includes(recherche)
                if (!matchNom && !matchNumero && !matchEmail) return false
            }
            if (filtresClients.ville !== 'tous' && c.ville !== filtresClients.ville) return false
            if (filtresClients.entreprise !== 'tous' && c.entreprise !== filtresClients.entreprise) return false
            if (filtresClients.segment !== 'tous' && c.segment !== filtresClients.segment) return false
            return true
        })
    }, [clients, filtresClients])

    const filtresClientsActifs =
        filtresClients.recherche !== '' ||
        filtresClients.ville !== 'tous' ||
        filtresClients.entreprise !== 'tous' ||
        filtresClients.segment !== 'tous'

    const toggleClient = (id) => {
        const ids = form.client_ids.includes(id)
            ? form.client_ids.filter(i => i !== id)
            : [...form.client_ids, id]
        setForm({ ...form, client_ids: ids })
    }

    const toutSelectionner = () => {
        const idsFiltres = clientsFiltres.map(c => c.id)
        const tousDejaSelectionnes = idsFiltres.every(id => form.client_ids.includes(id)) && idsFiltres.length > 0
        if (tousDejaSelectionnes) {
            setForm({ ...form, client_ids: form.client_ids.filter(id => !idsFiltres.includes(id)) })
        } else {
            setForm({ ...form, client_ids: [...new Set([...form.client_ids, ...idsFiltres])] })
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            const payload = {
                nom: form.nom,
                template: form.template || null,
            }
            await api.post('/campagnes/', payload)
            setMessage({ type: 'success', text: 'Campagne créée avec succès !' })
            setShowForm(false)
            setForm({ nom: '', template: '', client_ids: [] })
            setFiltresClients(FILTRES_CLIENTS_INITIAL)
            await chargerDonnees()
        } catch (err) {
            const erreur = err.response?.data?.erreur || 'Erreur lors de la création.'
            setMessage({ type: 'error', text: erreur })
        }
    }

    const templateDeLaCampagne = (campagne) => {
        return templates.find(t => t.id === campagne.template) || null
    }

    const templateNecessiteHeaderUrl = (campagne) => {
        const t = templateDeLaCampagne(campagne)
        return t && ['IMAGE', 'VIDEO', 'DOCUMENT'].includes(t.type_header)
    }

    const getMappingCampagne = (campagneId) => mappingVariables[campagneId] || {}

    const setMappingVariable = (campagneId, indexVariable, valeur) => {
        setMappingVariables(prev => ({
            ...prev,
            [campagneId]: {
                ...(prev[campagneId] || {}),
                [indexVariable]: valeur,
            }
        }))
    }

    const renderChampsMapping = (campagne) => {
        const template = templateDeLaCampagne(campagne)
        if (!template || !template.nombre_variables) return null

        const mapping = getMappingCampagne(campagne.id)

        return (
            <div>
                <p className="text-sm font-medium text-gray-700 mb-2">
                    Variables du message ({template.nombre_variables})
                </p>
                <div className="grid gap-3">
                    {Array.from({ length: template.nombre_variables }, (_, i) => i + 1).map(num => {
                        const cle = String(num)
                        const valeurActuelle = mapping[cle] || ''
                        const estFixe = valeurActuelle.startsWith('fixe:')

                        return (
                            <div key={num} className="flex items-center gap-3">
                                <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded shrink-0">
                                    {`{{${num}}}`}
                                </span>
                                <select
                                    value={estFixe ? 'fixe' : valeurActuelle}
                                    onChange={(e) => {
                                        const v = e.target.value
                                        setMappingVariable(campagne.id, cle, v === 'fixe' ? 'fixe:' : v)
                                    }}
                                    className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                >
                                    <option value="">-- Choisir une source --</option>
                                    {CHAMPS_CLIENT.map(champ => (
                                        <option key={champ.value} value={champ.value}>{champ.label}</option>
                                    ))}
                                    <option value="fixe">Valeur fixe...</option>
                                </select>
                                {estFixe && (
                                    <input
                                        type="text"
                                        value={valeurActuelle.replace('fixe:', '')}
                                        onChange={(e) => setMappingVariable(campagne.id, cle, `fixe:${e.target.value}`)}
                                        placeholder="Valeur fixe"
                                        className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                    />
                                )}
                            </div>
                        )
                    })}
                </div>
                <p className="text-xs text-gray-400 mt-2">
                    Chaque client recevra un message personnalisé selon ce mapping.
                </p>
            </div>
        )
    }

    const mappingComplet = (campagne) => {
        const template = templateDeLaCampagne(campagne)
        if (!template || !template.nombre_variables) return true
        const mapping = getMappingCampagne(campagne.id)
        for (let i = 1; i <= template.nombre_variables; i++) {
            const val = mapping[String(i)]
            if (!val || val === 'fixe:') return false
        }
        return true
    }

    const pollerProgression = (campagneId) => {
        const intervalId = setInterval(async () => {
            try {
                const res = await api.get(`/campagnes/${campagneId}/progression/`)
                if (res.data.termine) {
                    clearInterval(intervalId)
                    delete intervalsActifs.current[campagneId]
                    setEnvoyant(null)
                    setMessage({
                        type: res.data.statistiques.echec === 0 ? 'success' : 'error',
                        text: `Campagne terminée : ${res.data.statistiques.envoye + res.data.statistiques.lu} envoyés, ${res.data.statistiques.echec} échecs.`
                    })
                    await chargerDonnees()
                }
            } catch (err) {
                clearInterval(intervalId)
                delete intervalsActifs.current[campagneId]
                setEnvoyant(null)
                console.error(err)
            }
        }, 2000)
        intervalsActifs.current[campagneId] = intervalId
    }

    const lancerEnvoi = async (campagneId, campagneNom, campagne) => {
        if (!window.confirm(`Lancer l'envoi de "${campagneNom}" ?`)) return

        const template = templateDeLaCampagne(campagne)
        let mediaId = headerMediaIds[campagneId]

        if (templateNecessiteHeaderUrl(campagne)) {
            if (!mediaId && !headerFiles[campagneId]) {
                setMessage({
                    type: 'error',
                    text: `Le template de cette campagne a un header média. Choisissez un fichier avant d'envoyer.`
                })
                return
            }
            if (!mediaId) {
                mediaId = await uploaderMediaHeader(campagneId)
                if (!mediaId) return
            }
        }

        if (template?.nombre_variables > 0 && !mappingComplet(campagne)) {
            setMessage({
                type: 'error',
                text: `Complétez le mapping de toutes les variables avant d'envoyer.`
            })
            return
        }

        setEnvoyant(campagneId)
        try {
            const payload = {
                ...(form.client_ids.length > 0 ? { client_ids: form.client_ids } : {}),
                ...(mediaId ? { header_media_id: mediaId } : {}),
                ...(Object.keys(getMappingCampagne(campagneId)).length > 0
                    ? { mapping_variables: getMappingCampagne(campagneId) }
                    : {}),
            }
            await api.post(`/campagnes/${campagneId}/envoyer/`, payload)
            await chargerDonnees()
            pollerProgression(campagneId)
        } catch (err) {
            const erreur = err.response?.data?.erreur || 'Erreur lors de l\'envoi.'
            setMessage({ type: 'error', text: erreur })
            setEnvoyant(null)
        }
    }

    const voirDetail = async (campagneId) => {
        if (showDetail === campagneId) {
            setShowDetail(null)
            setDetail(null)
            return
        }
        try {
            const res = await api.get(`/campagnes/${campagneId}/detail/`)
            setDetail(res.data)
            setShowDetail(campagneId)
        } catch (err) {
            console.error(err)
        }
    }

    const statutsDisponibles = useMemo(
        () => [...new Set(campagnes.map((c) => c.statut))].sort(),
        [campagnes]
    )

    const campagnesFiltrees = useMemo(() => {
        const recherche = filtres.recherche.trim().toLowerCase()
        return campagnes.filter((c) => {
            if (recherche && !c.nom.toLowerCase().includes(recherche) && !c.template_nom?.toLowerCase().includes(recherche)) {
                return false
            }
            if (filtres.statut !== 'tous' && c.statut !== filtres.statut) return false
            return true
        })
    }, [campagnes, filtres])

    const filtresActifs = filtres.recherche !== '' || filtres.statut !== 'tous'

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-gray-800">Campagnes</h1>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition-colors"
                >
                    {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                    {showForm ? 'Annuler' : 'Nouvelle campagne'}
                </button>
            </div>

            {/* Message feedback */}
            {message && (
                <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
                    message.type === 'success'
                        ? 'bg-green-50 text-green-700 border border-green-200'
                        : 'bg-red-50 text-red-700 border border-red-200'
                }`}>
                    {message.text}
                    <button onClick={() => setMessage(null)} className="ml-3 text-xs underline">
                        Fermer
                    </button>
                </div>
            )}

            {/* Formulaire création */}
            {showForm && (
                <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-gray-800 mb-4">Nouvelle campagne</h2>
                    <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Nom</label>
                            <input
                                name="nom"
                                value={form.nom}
                                onChange={handleChange}
                                placeholder="ex: Promo Ramadan 2026"
                                required
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            />
                        </div>

                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Template</label>
                            <select
                                name="template"
                                value={form.template}
                                onChange={handleChange}
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                            >
                                <option value="">-- Choisir un template --</option>
                                {templates.map(t => (
                                    <option key={t.id} value={t.id}>
                                        {t.nom} ({t.langue}){['IMAGE','VIDEO','DOCUMENT'].includes(t.type_header) ? ` · média ${t.type_header}` : ''}
                                    </option>
                                ))}
                            </select>
                            <p className="text-xs text-gray-400 mt-1">
                                Les variables du template se configurent après création de la campagne.
                            </p>
                        </div>

                        <div className="col-span-2 flex justify-end">
                            <button
                                type="submit"
                                className="px-6 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 transition-colors"
                            >
                                Créer la campagne
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Filtres campagnes */}
            {!loading && campagnes.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm flex flex-col md:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            value={filtres.recherche}
                            onChange={(e) => setFiltres({ ...filtres, recherche: e.target.value })}
                            placeholder="Rechercher par nom ou template..."
                            className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                        />
                    </div>
                    <select
                        value={filtres.statut}
                        onChange={(e) => setFiltres({ ...filtres, statut: e.target.value })}
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                    >
                        <option value="tous">Tous les statuts</option>
                        {statutsDisponibles.map((s) => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                            {campagnesFiltrees.length} / {campagnes.length}
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

            {/* Liste campagnes */}
            {loading ? (
                <div className="flex flex-col items-center justify-center py-12">
                    <RefreshCw className="w-8 h-8 text-green-500 animate-spin mb-4" />
                    <p className="text-gray-500 font-medium">Chargement des campagnes...</p>
                </div>
            ) : campagnes.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                    <Send className="w-12 h-12 text-gray-300 mb-4" />
                    <p className="text-gray-500 font-medium mb-2">Aucune campagne trouvée</p>
                    <p className="text-gray-400 text-sm">Créez votre première campagne pour commencer</p>
                </div>
            ) : campagnesFiltrees.length === 0 ? (
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
                <div className="grid gap-4">
                    {campagnesFiltrees.map((c) => (
                        <div
                            key={c.id}
                            onClick={() => voirDetail(c.id)}
                            className="bg-white rounded-xl border border-gray-200 shadow-sm cursor-pointer hover:border-green-300 hover:shadow-md transition-all"
                        >
                            {/* En-tête campagne */}
                            <div className="flex items-start justify-between p-5">
                                <div className="flex-1">
                                    <h2 className="font-semibold text-gray-800">{c.nom}</h2>
                                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                                        <p className="text-sm text-gray-400">
                                            {c.date_creation ? new Date(c.date_creation).toLocaleDateString('fr-FR') : '—'}
                                        </p>
                                        {c.template_nom && (
                                            <span className="flex items-center gap-1 text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full border border-purple-100">
                                                <FileText className="w-3 h-3" /> {c.template_nom}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex gap-4 mt-2 text-xs">
                                        <span className="flex items-center gap-1 text-blue-600 font-medium">
                                            <Send className="w-3 h-3" /> {c.statistiques?.envoye || 0} envoyés
                                        </span>
                                        <span className="flex items-center gap-1 text-green-600 font-medium">
                                            <CheckCircle className="w-3 h-3" /> {c.statistiques?.lu || 0} lus
                                        </span>
                                        <span className="flex items-center gap-1 text-red-500 font-medium">
                                            <XCircle className="w-3 h-3" /> {c.statistiques?.echec || 0} échecs
                                        </span>
                                    </div>
                                </div>

                                <div className="flex gap-2 ml-4 items-center shrink-0">
                                    <span className={`text-xs px-2 py-1 rounded-full font-medium border ${couleurStatut(c.statut)}`}>
                                        {c.statut}
                                    </span>
                                    {(c.statut === 'brouillon' || c.statut === 'partiel' || c.statut === 'echec' || c.statut === 'en_cours') && (
                                        <button
                                            onClick={(e) => { e.stopPropagation(); lancerEnvoi(c.id, c.nom, c) }}
                                            disabled={envoyant === c.id || uploadingMedia === c.id}
                                            className="text-xs px-3 py-1 rounded-lg bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
                                        >
                                            {uploadingMedia === c.id ? 'Upload média...' : envoyant === c.id ? 'Envoi...' : 'Lancer'}
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Zone de préparation avant envoi */}
                            {(c.statut === 'brouillon' || c.statut === 'partiel' || c.statut === 'echec') && (
                                <div
                                    onClick={(e) => e.stopPropagation()}
                                    className="border-t border-gray-100 px-5 py-4 space-y-4"
                                >
                                    {renderChampsMapping(c)}

                                    {templateNecessiteHeaderUrl(c) && (
                                        <div>
                                            <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1">
                                                <ImageIcon className="w-4 h-4" /> Fichier média du header
                                                <span className="text-red-500">*</span>
                                                <span className="text-xs font-normal text-gray-400">
                                                    (obligatoire — ce template a un header {templateDeLaCampagne(c)?.type_header})
                                                </span>
                                            </label>
                                            <input
                                                type="file"
                                                accept="image/jpeg,image/png,video/mp4,application/pdf"
                                                onChange={(e) => {
                                                    const fichier = e.target.files[0]
                                                    setHeaderFiles(prev => ({ ...prev, [c.id]: fichier }))
                                                    setHeaderMediaIds(prev => ({ ...prev, [c.id]: null }))
                                                }}
                                                className="w-full border border-orange-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 bg-orange-50"
                                            />
                                            {uploadingMedia === c.id && (
                                                <p className="text-xs text-orange-500 mt-1">Upload du média en cours…</p>
                                            )}
                                            {headerMediaIds[c.id] && (
                                                <p className="flex items-center gap-1 text-xs text-green-600 mt-1">
                                                    <CheckCircle className="w-3.5 h-3.5" /> Média déjà uploadé chez Meta (id: {headerMediaIds[c.id]})
                                                </p>
                                            )}
                                            <p className="text-xs text-gray-400 mt-1">
                                                Le fichier sera uploadé directement chez Meta lors de l'envoi de la campagne.
                                            </p>
                                        </div>
                                    )}

                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <p className="text-sm font-medium text-gray-700">
                                                Sélectionner les clients
                                                {form.client_ids.length > 0 && (
                                                    <span className="ml-2 text-green-600">({form.client_ids.length} sélectionnés)</span>
                                                )}
                                            </p>
                                            <button
                                                onClick={toutSelectionner}
                                                className="text-xs text-gray-500 hover:text-gray-700 underline"
                                            >
                                                Tout sélectionner / désélectionner (filtrés)
                                            </button>
                                        </div>

                                        {/* Filtres multi-critères clients */}
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
                                            <input
                                                type="text"
                                                value={filtresClients.recherche}
                                                onChange={(e) => setFiltresClients({ ...filtresClients, recherche: e.target.value })}
                                                placeholder="Nom, numéro, email..."
                                                className="col-span-2 md:col-span-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                            />
                                            <select
                                                value={filtresClients.ville}
                                                onChange={(e) => setFiltresClients({ ...filtresClients, ville: e.target.value })}
                                                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                            >
                                                <option value="tous">Toutes les villes</option>
                                                {villesDisponibles.map(v => <option key={v} value={v}>{v}</option>)}
                                            </select>
                                            <select
                                                value={filtresClients.entreprise}
                                                onChange={(e) => setFiltresClients({ ...filtresClients, entreprise: e.target.value })}
                                                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                            >
                                                <option value="tous">Toutes les entreprises</option>
                                                {entreprisesDisponibles.map(v => <option key={v} value={v}>{v}</option>)}
                                            </select>
                                            <select
                                                value={filtresClients.segment}
                                                onChange={(e) => setFiltresClients({ ...filtresClients, segment: e.target.value })}
                                                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                                            >
                                                <option value="tous">Tous les segments</option>
                                                {segmentsDisponibles.map(v => <option key={v} value={v}>{v}</option>)}
                                            </select>
                                        </div>

                                        {filtresClientsActifs && (
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-xs text-gray-400">{clientsFiltres.length} client(s) correspondant</span>
                                                <button
                                                    onClick={() => setFiltresClients(FILTRES_CLIENTS_INITIAL)}
                                                    className="text-xs text-gray-500 hover:text-gray-700 underline"
                                                >
                                                    Réinitialiser les filtres
                                                </button>
                                            </div>
                                        )}

                                        <div className="max-h-48 overflow-y-auto grid gap-1">
                                            {clientsFiltres.map(client => (
                                                <label
                                                    key={client.id}
                                                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={form.client_ids.includes(client.id)}
                                                        onChange={() => toggleClient(client.id)}
                                                        className="accent-green-500"
                                                    />
                                                    <span className="text-sm text-gray-700">{client.nom}</span>
                                                    <span className="text-xs text-gray-400">{client.numero}</span>
                                                </label>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Détail envois */}
                            {showDetail === c.id && detail && (
                                <div
                                    onClick={(e) => e.stopPropagation()}
                                    className="border-t border-gray-100 px-5 py-4"
                                >
                                    <div className="flex gap-4 mb-4 text-sm flex-wrap">
                                        <div className="bg-gray-50 rounded-lg px-4 py-2 border border-gray-100">
                                            <span className="text-gray-500">Template : </span>
                                            <span className="font-medium text-purple-700">{detail.template || '—'}</span>
                                        </div>
                                        <div className="bg-blue-50 rounded-lg px-4 py-2 border border-blue-100">
                                            <span className="text-gray-500">Envoyés : </span>
                                            <span className="font-medium text-blue-700">{detail.statistiques?.envoye || 0}</span>
                                        </div>
                                        <div className="bg-green-50 rounded-lg px-4 py-2 border border-green-100">
                                            <span className="text-gray-500">Lus : </span>
                                            <span className="font-medium text-green-700">{detail.statistiques?.lu || 0}</span>
                                        </div>
                                        <div className="bg-red-50 rounded-lg px-4 py-2 border border-red-100">
                                            <span className="text-gray-500">Échecs : </span>
                                            <span className="font-medium text-red-700">{detail.statistiques?.echec || 0}</span>
                                        </div>
                                    </div>

                                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Détail par client</h3>
                                    <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-100">
                                        <table className="w-full text-sm">
                                            <thead className="bg-gray-50 sticky top-0">
                                            <tr>
                                                <th className="text-left px-3 py-2 text-gray-600 font-medium">Client</th>
                                                <th className="text-left px-3 py-2 text-gray-600 font-medium">Numéro</th>
                                                <th className="text-left px-3 py-2 text-gray-600 font-medium">Statut</th>
                                                <th className="text-left px-3 py-2 text-gray-600 font-medium">Raison d'échec</th>
                                            </tr>
                                            </thead>
                                            <tbody>
                                            {detail.envois.map((envoi, i) => (
                                                <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                                    <td className="px-3 py-2 font-medium text-gray-800">{envoi.client_nom}</td>
                                                    <td className="px-3 py-2 text-gray-500">{envoi.client_numero}</td>
                                                    <td className={`px-3 py-2 font-medium ${couleurEnvoi(envoi.statut)}`}>
                                                        {envoi.statut}
                                                    </td>
                                                    <td className="px-3 py-2 text-xs">
                                                        {envoi.erreur
                                                            ? <span className="text-red-600 bg-red-50 px-2 py-1 rounded border border-red-100">{envoi.erreur}</span>
                                                            : <span className="text-gray-300">—</span>
                                                        }
                                                    </td>
                                                </tr>
                                            ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default Campagnes