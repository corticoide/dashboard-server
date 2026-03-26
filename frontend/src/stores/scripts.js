import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useScriptsStore = defineStore('scripts', () => {
  const favorites = ref([])
  const loaded = ref(false)

  const favoritePaths = computed(() => new Set(favorites.value.map(f => f.path)))

  function isFavorite(path) {
    return favoritePaths.value.has(path)
  }

  function getFavoriteId(path) {
    return favorites.value.find(f => f.path === path)?.id ?? null
  }

  async function loadFavorites(force = false) {
    if (loaded.value && !force) return
    try {
      const { data } = await api.get('/scripts/favorites')
      favorites.value = data
      loaded.value = true
    } catch {}
  }

  async function addFavorite(path) {
    try {
      const { data } = await api.post('/scripts/favorites', { path })
      // Replace if already exists, otherwise push
      const idx = favorites.value.findIndex(f => f.path === path)
      if (idx >= 0) favorites.value[idx] = data
      else favorites.value.push(data)
    } catch (e) {
      console.error('addFavorite failed', e)
    }
  }

  async function removeFavoriteByPath(path) {
    const fav = favorites.value.find(f => f.path === path)
    if (!fav) return
    try {
      await api.delete(`/scripts/favorites/${fav.id}`)
      favorites.value = favorites.value.filter(f => f.id !== fav.id)
    } catch (e) {
      console.error('removeFavorite failed', e)
    }
  }

  async function updateFavorite(id, patch) {
    const { data } = await api.patch(`/scripts/favorites/${id}`, patch)
    const idx = favorites.value.findIndex(f => f.id === id)
    if (idx >= 0) favorites.value[idx] = data
    return data
  }

  return {
    favorites,
    loaded,
    favoritePaths,
    isFavorite,
    getFavoriteId,
    loadFavorites,
    addFavorite,
    removeFavoriteByPath,
    updateFavorite,
  }
})
