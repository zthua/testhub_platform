import request from '@/utils/api'

/**
 * 签名配置管理 API
 */

// 获取签名配置列表
export const getSignatureConfigs = (params) => {
  return request({
    url: '/signature-configs/',
    method: 'get',
    params
  })
}

// 获取签名配置详情
export const getSignatureConfig = (id) => {
  return request({
    url: `/signature-configs/${id}/`,
    method: 'get'
  })
}

// 创建签名配置
export const createSignatureConfig = (data) => {
  return request({
    url: '/signature-configs/',
    method: 'post',
    data
  })
}

// 更新签名配置
export const updateSignatureConfig = (id, data) => {
  return request({
    url: `/signature-configs/${id}/`,
    method: 'put',
    data
  })
}

// 删除签名配置
export const deleteSignatureConfig = (id) => {
  return request({
    url: `/signature-configs/${id}/`,
    method: 'delete'
  })
}

// 设置为默认配置
export const setDefaultSignatureConfig = (id) => {
  return request({
    url: `/signature-configs/${id}/set_default/`,
    method: 'post'
  })
}

// 测试签名生成
export const testSignature = (id, data) => {
  return request({
    url: `/signature-configs/${id}/test_signature/`,
    method: 'post',
    data
  })
}

/**
 * 参数化函数列表（用于前端提示）
 */
export const PARAMETER_FUNCTIONS = [
  {
    name: 'get_id',
    syntax: ':${get_id()}',
    description: '生成随机数字ID',
    example: ':${get_id(10)}',
    category: 'ID生成'
  },
  {
    name: 'get_uuid',
    syntax: ':${get_uuid()}',
    description: '生成UUID',
    example: ':${get_uuid()}',
    category: 'ID生成'
  },
  {
    name: 'get_uuid_short',
    syntax: ':${get_uuid_short()}',
    description: '生成短UUID（无横线）',
    example: ':${get_uuid_short()}',
    category: 'ID生成'
  },
  {
    name: 'get_timestamp',
    syntax: ':${get_timestamp()}',
    description: '获取当前时间戳（秒）',
    example: ':${get_timestamp()}',
    category: '时间日期'
  },
  {
    name: 'get_timestamp_ms',
    syntax: ':${get_timestamp_ms()}',
    description: '获取当前时间戳（毫秒）',
    example: ':${get_timestamp_ms()}',
    category: '时间日期'
  },
  {
    name: 'get_datetime',
    syntax: ':${get_datetime()}',
    description: '获取当前日期时间',
    example: ':${get_datetime(%Y-%m-%d %H:%M:%S)}',
    category: '时间日期'
  },
  {
    name: 'get_date',
    syntax: ':${get_date()}',
    description: '获取当前日期',
    example: ':${get_date()}',
    category: '时间日期'
  },
  {
    name: 'get_time',
    syntax: ':${get_time()}',
    description: '获取当前时间',
    example: ':${get_time()}',
    category: '时间日期'
  },
  {
    name: 'get_random_string',
    syntax: ':${get_random_string(10)}',
    description: '生成随机字符串',
    example: ':${get_random_string(16)}',
    category: '随机生成'
  },
  {
    name: 'get_random_int',
    syntax: ':${get_random_int(0,100)}',
    description: '生成随机整数',
    example: ':${get_random_int(1,999)}',
    category: '随机生成'
  },
  {
    name: 'get_random_float',
    syntax: ':${get_random_float(0,100,2)}',
    description: '生成随机浮点数',
    example: ':${get_random_float(0,1,3)}',
    category: '随机生成'
  },
  {
    name: 'get_email',
    syntax: ':${get_email()}',
    description: '生成随机邮箱',
    example: ':${get_email(test.com)}',
    category: '业务数据'
  },
  {
    name: 'get_phone',
    syntax: ':${get_phone()}',
    description: '生成随机手机号',
    example: ':${get_phone(138)}',
    category: '业务数据'
  }
]

/**
 * 获取参数化函数分类
 */
export const getParameterFunctionsByCategory = () => {
  const categories = {}
  PARAMETER_FUNCTIONS.forEach(func => {
    if (!categories[func.category]) {
      categories[func.category] = []
    }
    categories[func.category].push(func)
  })
  return categories
}
