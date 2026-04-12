"""
models/word_completer.py -- Completion locale de mots par Trie.

Construit un dictionnaire a partir du texte du document en cours
et propose des completions instantanees (< 5ms).
"""

import re
import unicodedata


class _TrieNode:
    __slots__ = ("children", "is_word", "freq")

    def __init__(self):
        self.children: dict[str, "_TrieNode"] = {}
        self.is_word: bool = False
        self.freq: int = 0


class WordCompleter:
    """Trie-based word completer avec frequences."""

    # Mots francais courants pour amorcer le dictionnaire
    _COMMON_FR = (
        "le la les un une des de du en et est au aux ce ces cette cet"
        " il elle on nous vous ils elles je tu son sa ses leur leurs"
        " que qui dont ou mais pour par sur dans avec sans plus moins"
        " tout tous toute toutes autre autres meme bien fait faire"
        " avoir etre comme aussi encore entre avant apres depuis"
        " pouvoir vouloir devoir savoir aller dire voir prendre"
        " donner falloir parler mettre passer venir tenir suivre"
        " comprendre connaitre croire trouver partir sortir vivre"
        " ecrire lire ouvrir attendre entendre perdre repondre"
        " rester tomber devenir revenir sentir servir recevoir"
        " commencer finir choisir reussir agir remplir"
        " cependant toutefois neanmoins pourtant donc ainsi"
        " alors ensuite enfin premierement deuxiemement"
        " quelque plusieurs certain chaque aucun"
        " toujours souvent parfois jamais deja bientot"
        " vraiment seulement simplement exactement"
        " aujourd'hui maintenant hier demain"
        " bonjour merci monsieur madame"
        " nouveau nouvelle petit petite grand grande"
        " bon bonne mauvais mauvaise premier premiere dernier derniere"
        " important possible different difficile necessaire"
        " exemple question probleme solution resultat"
        " travail temps nombre partie point nombre"
        " monde pays ville maison famille personne"
        " information communication organisation situation"
        " developpement fonctionnement changement mouvement"
        " egalement notamment particulierement"
        " actuellement effectivement naturellement"
        " malheureusement heureusement certainement"
        " probablement evidemment absolument"
        " parce puisque lorsque quand comment pourquoi"
        " beaucoup trop assez peu tres"
    )

    def __init__(self):
        self._root = _TrieNode()
        self._word_set: set[str] = set()
        # Amorcer avec les mots courants
        for w in self._COMMON_FR.split():
            self._insert(w, freq=1)

    def _insert(self, word: str, freq: int = 1):
        node = self._root
        for ch in word.lower():
            if ch not in node.children:
                node.children[ch] = _TrieNode()
            node = node.children[ch]
        node.is_word = True
        node.freq += freq

    def update_from_text(self, text: str):
        """Reconstruit le trie a partir du texte du document."""
        words = re.findall(r"[a-zA-ZàâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ'']+", text)
        new_words = set()
        for w in words:
            low = w.lower()
            if len(low) >= 2:
                new_words.add(low)

        # Ajouter les nouveaux mots (incremental)
        for w in new_words - self._word_set:
            self._insert(w)
        self._word_set = new_words

        # Re-compter les frequences depuis le texte
        freq_map: dict[str, int] = {}
        for w in words:
            low = w.lower()
            if len(low) >= 2:
                freq_map[low] = freq_map.get(low, 0) + 1

        # Mettre a jour les frequences dans le trie
        for w, f in freq_map.items():
            node = self._root
            for ch in w:
                if ch in node.children:
                    node = node.children[ch]
                else:
                    break
            else:
                if node.is_word:
                    node.freq = f

    def complete(self, prefix: str, max_results: int = 6) -> list[str]:
        """Retourne les completions triees par frequence decroissante."""
        if len(prefix) < 2:
            return []

        prefix_low = prefix.lower()
        node = self._root
        for ch in prefix_low:
            if ch not in node.children:
                return []
            node = node.children[ch]

        # Collecter tous les mots sous ce noeud
        results: list[tuple[str, int]] = []
        self._collect(node, prefix_low, results, max_results * 3)

        # Trier par frequence decroissante, exclure le prefix exact
        results.sort(key=lambda x: -x[1])
        return [w for w, _ in results if w != prefix_low][:max_results]

    def _collect(self, node: _TrieNode, prefix: str,
                 results: list[tuple[str, int]], limit: int):
        if len(results) >= limit:
            return
        if node.is_word:
            results.append((prefix, node.freq))
        for ch, child in node.children.items():
            if len(results) >= limit:
                return
            self._collect(child, prefix + ch, results, limit)
