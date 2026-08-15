/**
 * axios 封装：统一处理后端 {ok, data, message} 响应结构。
 * - 成功(ok=true)：resolve 返回 data
 * - 失败(ok=false)：reject 携带 message
 * baseURL 走相对 /api，由 vite dev proxy 转发到 8800。
 */
import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    // 非统一结构（如文件下载）直接返回原始响应
    if (body == null || typeof body.ok === 'undefined') {
      return resp
    }
    if (body.ok) {
      return body.data
    }
    return Promise.reject(new Error(body.message || '请求失败'))
  },
  (error) => {
    const msg = error?.response?.data?.message || error.message || '网络错误'
    return Promise.reject(new Error(msg))
  },
)

export function get(url, params) {
  return http.get(url, { params })
}

export function post(url, data) {
  return http.post(url, data)
}

export function put(url, data) {
  return http.put(url, data)
}

export function del(url) {
  return http.delete(url)
}

export default http