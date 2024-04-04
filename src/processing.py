import asyncio
import re
import httpx
import spacy
import json
import unicodedata

import collections
from nltk.corpus import mac_morpho
from spellchecker import SpellChecker
from bs4 import BeautifulSoup
from functools import lru_cache, wraps
from time import perf_counter


def timing(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = await func(*args, **kwargs)
        end_time = perf_counter()
        elapsed_time_ms = round(((end_time - start_time) * 1000), 2)
        print(f"A função '{func.__name__}' foi executada em: {elapsed_time_ms} ms")
        return result, elapsed_time_ms

    return wrapper


class Processing:
    def __init__(self, url, section, tag) -> None:
        self._url = url
        self._section = section
        self._tag = tag
        self._expansion_dict_file = "src/words.json"

    async def __init_processing(self):
        WORDS = self.tokens(" ".join(mac_morpho.words()))
        WORD_COUNTS = collections.Counter(WORDS)
        self._words_counts = WORD_COUNTS
        """Inicialização das função de processamento dos dados"""
        self._raspagem = await self.__raspagem()
        self._remocao_ruido = await self.__remocao_ruido()
        self._tokenizacao_frases = await self.__tokenizacao_por_frases()
        self._tokenizacao_palavras = await self.__tokenizacao_por_palavras()
        self._expansao_palavras = await self.__expansao_palavras()
        self._correcao_palavras = await self.__correcao_palavras()
        self._correcao_palavras_lib = await self.__correcao_palavras_lib()

    @timing
    async def __raspagem(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(self._url)
            if response.status_code == 200:
                return response.content
            else:
                return None

    @timing
    async def __remocao_ruido(self):
        soup = BeautifulSoup(self._raspagem[0], "html.parser")
        [s.extract() for s in soup(["iframe", "script"])]

        session = soup.find(self._tag, self._section)

        if session is None:
            session = soup.find(self._tag, id=self._section)

        if session:
            stripped_text = session.get_text()
            stripped_text = re.sub(r"\s+", " ", stripped_text)
            stripped_text = stripped_text.replace("\n", " ")
            return stripped_text.strip()
        else:
            stripped_text = soup.get_text()
            stripped_text = re.sub(r"[\r|\n|\r\n]", "\n", stripped_text)
            return stripped_text

    @timing
    async def __tokenizacao_por_frases(self):
        try:
            """Separação das frases que vem da remoção de ruido, onde ele vai devolver todas as frases separadas pelas pontuação"""
            model_spacy = spacy.load("pt_core_news_sm")
            word_tokens = model_spacy(self._remocao_ruido[0])
            sentences = [
                self.remove_special_characters(str(sent)) for sent in word_tokens.sents
            ]
            sentence_tokens = sentences
            return sentence_tokens
        except Exception as e:
            print(e)

    @timing
    async def __tokenizacao_por_palavras(self):
        try:
            """Criação de Vetor de vetores com as palavras de cada frase"""
            sentences = [lst for lst in self._tokenizacao_frases[0] if lst]
            words_tokens = [frase.split() for frase in sentences]
            return words_tokens
        except Exception as e:
            print(e)

    @timing
    async def __expansao_palavras(self):
        try:
            """Função para expandir palavras e corrigir acentuação"""
            expansion_dict: dict = self.load_expansion_dict(self._expansion_dict_file)
            all_words = [word[:] for word in self._tokenizacao_palavras[0] if word]
            expanded_tokenizacao_palavras = []

            for words in all_words:
                expanded_words = []
                for i, word in enumerate(words):
                    expanded_word = self.expand_word(word.lower(), expansion_dict)
                    words[i] = expanded_word
                    expanded_words.append(expanded_word)
                expanded_tokenizacao_palavras.append(expanded_words)

            return expanded_tokenizacao_palavras
        except Exception as e:
            print(e)

    @timing
    async def __correcao_palavras_lib(self):
        try:
            portuguese = SpellChecker(language="pt")
            all_words = self._expansao_palavras[0]
            correcao_palavra_list = []

            @lru_cache(maxsize=None)
            def correcao_palavra(word):
                correction_word = portuguese.correction(word)
                return correction_word if correction_word is not None else word

            for words in all_words:
                correcao_lista = [correcao_palavra(word) for word in words]
                correcao_palavra_list.append(correcao_lista)

            return correcao_palavra_list
        except Exception as e:
            print(e)

    @timing
    async def __correcao_palavras(self):
        try:
            all_words = self._expansao_palavras[0]
            correcao_palavra_list = []

            async def correcao_palavra(word, max_dist=2):
                best_word = word
                best_count = self._words_counts.get(word, 0)
                for dist in range(1, max_dist + 1):
                    for edit in self.edits_up_to_n(word, dist):
                        count = self._words_counts.get(edit, 0)
                        if count > best_count:
                            best_word = edit
                            best_count = count
                if best_word is not None:
                    return best_word
                else:
                    return word

            async def correcao_palavras_para_uma_lista(words):
                return await asyncio.gather(*[correcao_palavra(word) for word in words])

            correcao_palavra_list = await asyncio.gather(
                *[correcao_palavras_para_uma_lista(words) for words in all_words]
            )

            return correcao_palavra_list
        except Exception as e:
            print(f"Correção de palavras: {e}")

    async def generate_candidates(self, word, max_dist):
        candidates = await self.known(self.edits0(word))
        for dist in range(1, max_dist + 1):
            for edit in self.edits_up_to_n(word, dist):
                candidates.append(edit)
        return candidates

    async def known(self, words):
        return [w for w in words if w in self._words_counts]

    def correct(self, word):
        candidates = (
            self.known(self.edits0(word)) or self.known(self.edits1(word)) or [word]
        )
        return max(candidates, key=self._words_counts.get)

    @staticmethod
    def edits0(word):
        return {word}

    @staticmethod
    def edits1(palavra):
        letras = "abcdefghijklmnopqrstuvwxyz"
        splits = [(palavra[:i], palavra[i:]) for i in range(len(palavra) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letras]
        inserts = [L + c + R for L, R in splits for c in letras]
        return set(deletes + transposes + replaces + inserts)

    @staticmethod
    def edits_up_to_n(word, n):
        if n == 1:
            return Processing.edits1(word)
        else:
            edits = Processing.edits1(word)
            for _ in range(n - 1):
                new_edits = set()
                for edit in edits:
                    new_edits.update(Processing.edits1(edit))
                edits.update(new_edits)
            return edits

    @staticmethod
    def load_expansion_dict(expansion_dict_file):
        """Carrega o dicionário de expansão de palavras do arquivo"""
        with open(expansion_dict_file, "r", encoding="utf-8") as f:
            expansion_dict = json.load(f)
        return expansion_dict

    @staticmethod
    def expand_word(word, expansion_dict):
        get_value = expansion_dict.get(word)
        if expansion_dict.get(word) is not None:
            return get_value
        else:
            return word

    @staticmethod
    def tokens(text):
        return re.findall("[a-z]+", text.lower())

    @staticmethod
    def remove_special_characters(text):
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("utf-8", "ignore")
        )
        special_chars_regex = r"[^a-zA-Z\s]"
        text_cleaned = re.sub(special_chars_regex, " ", text)

        return text_cleaned

    def __create_dict(self, entrada, saida, etapa):
        return {
            "entrada": entrada,
            "saida": saida[0],
            "tempo": saida[1],
            "etapa": etapa,
        }

    async def processing(self):
        await self.__init_processing()

        steps = [
            ("Raspagem", self._url, self._raspagem),
            ("Remoção de ruído", self._raspagem[0], self._remocao_ruido),
            (
                "Tokenização por frases",
                self._remocao_ruido[0],
                self._tokenizacao_frases,
            ),
            (
                "Tokenização por palavras",
                self._tokenizacao_frases[0],
                self._tokenizacao_palavras,
            ),
            (
                "Expansão de siglas e abreviaturas",
                self._tokenizacao_palavras[0],
                self._expansao_palavras,
            ),
            (
                "Correção de caracteres incorretos sem biblioteca",
                self._expansao_palavras[0],
                self._correcao_palavras,
            ),
            (
                "Correção de caracteres incorretos com biblioteca",
                self._expansao_palavras[0],
                self._correcao_palavras_lib,
            ),
        ]

        return [
            self.__create_dict(entrada, saida_func, etapa)
            for etapa, entrada, saida_func in steps
        ]
