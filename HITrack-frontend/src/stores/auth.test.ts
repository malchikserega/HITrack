import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    post: vi.fn(),
    get: vi.fn(),
    defaults: { headers: { common: {} as Record<string, string> } },
  },
}))

vi.mock('../plugins/axios', () => ({ default: apiMock }))

const stored = new Map<string, string>()
const sessionStorageMock: Storage = {
  get length() { return stored.size },
  clear: () => stored.clear(),
  getItem: (key) => stored.get(key) ?? null,
  key: (index) => [...stored.keys()][index] ?? null,
  removeItem: (key) => { stored.delete(key) },
  setItem: (key, value) => { stored.set(key, String(value)) },
}
Object.defineProperty(globalThis, 'sessionStorage', { value: sessionStorageMock })

import { useAuthStore } from './auth'

const user = {
  id: 7,
  username: 'operator',
  email: 'operator@example.test',
  groups: ['operator'],
  can_write: true,
  is_admin: false,
}

describe('authentication store', () => {
  beforeEach(() => {
    stored.clear()
    vi.clearAllMocks()
    apiMock.defaults.headers.common = {}
    setActivePinia(createPinia())
  })

  it('stores only the access token and loads current authorization data after login', async () => {
    apiMock.post.mockResolvedValueOnce({ data: { access: 'access-token' } })
    apiMock.get.mockResolvedValueOnce({ data: user })
    const store = useAuthStore()

    await expect(store.login('operator', 'password')).resolves.toEqual({ success: true })

    expect(store.token).toBe('access-token')
    expect(store.refreshToken).toBeNull()
    expect(sessionStorage.getItem('token')).toBe('access-token')
    expect(apiMock.defaults.headers.common.Authorization).toBe('Bearer access-token')
    expect(store.currentUser).toEqual(user)
    expect(store.canWrite).toBe(true)
    expect(store.isAdmin).toBe(false)
  })

  it('clears stale session state when login fails', async () => {
    sessionStorage.setItem('token', 'stale-token')
    apiMock.post.mockRejectedValueOnce({ response: { data: { detail: 'Invalid credentials' } } })
    const store = useAuthStore()

    await expect(store.login('operator', 'wrong')).resolves.toEqual({
      success: false,
      error: 'Invalid credentials',
    })

    expect(store.token).toBeNull()
    expect(sessionStorage.getItem('token')).toBeNull()
    expect(apiMock.defaults.headers.common.Authorization).toBeUndefined()
  })

  it('refreshes through the HttpOnly cookie endpoint and replaces the access token', async () => {
    apiMock.post.mockResolvedValueOnce({ data: { access: 'fresh-access' } })
    apiMock.get.mockResolvedValueOnce({ data: user })
    const store = useAuthStore()

    await expect(store.refreshAuth()).resolves.toBe(true)

    expect(apiMock.post).toHaveBeenCalledWith('auth/token/refresh/')
    expect(store.token).toBe('fresh-access')
    expect(sessionStorage.getItem('token')).toBe('fresh-access')
    expect(store.user).toEqual(user)
  })

  it('clears the session if refresh fails', async () => {
    sessionStorage.setItem('token', 'expired')
    apiMock.post.mockRejectedValueOnce(new Error('expired'))
    const store = useAuthStore()

    await expect(store.refreshAuth()).resolves.toBe(false)

    expect(store.isAuthenticated).toBe(false)
    expect(sessionStorage.getItem('token')).toBeNull()
  })

  it('always clears local authorization state even when logout request fails', async () => {
    sessionStorage.setItem('token', 'access')
    apiMock.post.mockRejectedValueOnce(new Error('network failure'))
    const store = useAuthStore()

    await expect(store.logout()).rejects.toThrow('network failure')

    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
    expect(sessionStorage.getItem('token')).toBeNull()
  })
})
