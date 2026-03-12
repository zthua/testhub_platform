<template>
  <div class="signature-management">
    <!-- 调试信息：显示加载状态和数据状态 -->
    <div style="background: #f5f5f5; padding: 10px; margin-bottom: 10px; border-radius: 4px;">
      <strong>调试信息：</strong><br>
      加载状态: {{ loading }}<br>
      数据数量: {{ signatureConfigs.length }}<br>
      项目数量: {{ projects.length }}
    </div>

    <div class="page-header">
      <h2>签名配置管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新建签名配置
      </el-button>
    </div>

    <!-- 加载状态 -->
    <div v-show="loading" style="text-align: center; padding: 20px;">
      <el-icon class="is-loading" :size="30"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <!-- 签名配置列表 -->
    <el-table
      :data="signatureConfigs"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="name" label="配置名称" width="200" />
      <el-table-column prop="project_name" label="所属项目" width="150" />
      <el-table-column prop="algorithm_display" label="签名算法" width="120" />
      <el-table-column prop="signature_field" label="签名字段名" width="150" />
      <el-table-column prop="signature_location_display" label="签名位置" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'">
            {{ row.is_enabled ? '启用' : '禁用' }}
          </el-tag>
          <el-tag v-if="row.is_default" type="warning" size="small" style="margin-left: 8px;">
            默认
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="testSignature(row)">
            测试签名
          </el-button>
          <el-button link type="primary" size="small" @click="editConfig(row)">
            编辑
          </el-button>
          <el-button link type="success" size="small" @click="setDefault(row)" v-if="!row.is_default">
            设为默认
          </el-button>
          <el-button link type="danger" size="small" @click="deleteConfig(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无签名配置，点击右上角新建" />
      </template>
    </el-table>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入配置名称" />
        </el-form-item>

        <el-form-item label="所属项目" prop="project">
          <el-select v-model="formData.project" placeholder="请选择项目" style="width: 100%;">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="签名算法" prop="algorithm">
          <el-select v-model="formData.algorithm" placeholder="请选择算法" style="width: 100%;" @change="handleAlgorithmChange">
            <el-option label="MD5" value="MD5" />
            <el-option label="SHA1" value="SHA1" />
            <el-option label="SHA256" value="SHA256" />
            <el-option label="HMAC-SHA1" value="HMAC-SHA1" />
            <el-option label="HMAC-SHA256" value="HMAC-SHA256" />
            <el-option label="RSA-SHA256" value="RSA-SHA256" />
            <el-option label="RSA-SHA512" value="RSA-SHA512" />
            <el-option label="RSA-MD5" value="RSA-MD5" />
            <el-option label="SM2" value="SM2" />
          </el-select>
        </el-form-item>

        <el-form-item label="签名密钥" prop="secret_key" v-if="formData.algorithm?.startsWith('HMAC')">
          <el-input
            v-model="formData.secret_key"
            type="password"
            placeholder="请输入HMAC签名密钥"
            show-password
          />
          <div class="form-tip">HMAC算法需要提供密钥</div>
        </el-form-item>

        <el-form-item label="RSA私钥" prop="rsa_private_key" v-if="formData.algorithm?.startsWith('RSA')">
          <el-input
            v-model="formData.rsa_private_key"
            type="textarea"
            :rows="6"
            placeholder="请输入RSA私钥（PEM格式）"
          />
          <div class="form-tip">RSA签名需要提供私钥</div>
        </el-form-item>

        <el-form-item label="RSA公钥" prop="rsa_public_key" v-if="formData.algorithm?.startsWith('RSA')">
          <el-input
            v-model="formData.rsa_public_key"
            type="textarea"
            :rows="6"
            placeholder="请输入RSA公钥（PEM格式，可选）"
          />
          <div class="form-tip">用于验证签名（可选）</div>
        </el-form-item>

        <el-form-item label="RSA加密公钥" prop="rsa_encrypt_public_key">
          <el-input
            v-model="formData.rsa_encrypt_public_key"
            type="textarea"
            :rows="6"
            placeholder="请输入RSA加密公钥（PEM格式）"
          />
          <div class="form-tip">用于加密${Enc(...)}参数（可选）</div>
        </el-form-item>

        <el-form-item label="SM2私钥" prop="sm2_private_key" v-if="formData.algorithm === 'SM2'">
          <el-input
            v-model="formData.sm2_private_key"
            placeholder="请输入SM2私钥（十六进制字符串）"
          />
          <div class="form-tip">SM2签名需要提供私钥（32字节十六进制）</div>
        </el-form-item>

        <el-form-item label="SM2公钥" prop="sm2_public_key" v-if="formData.algorithm === 'SM2'">
          <el-input
            v-model="formData.sm2_public_key"
            placeholder="请输入SM2公钥（十六进制字符串，可选）"
          />
          <div class="form-tip">用于验证签名（64字节十六进制）</div>
        </el-form-item>

        <el-form-item label="SM2模式" prop="sm2_mode" v-if="formData.algorithm === 'SM2'">
          <el-radio-group v-model="formData.sm2_mode">
            <el-radio value="C1C2C3">C1C2C3 (新标准)</el-radio>
            <el-radio value="C1C3C2">C1C3C2 (旧标准)</el-radio>
          </el-radio-group>
          <div class="form-tip">C1C2C3是新的国密标准</div>
        </el-form-item>

        <el-form-item label="签名位置" prop="signature_location">
          <el-select v-model="formData.signature_location" placeholder="请选择位置" style="width: 100%;">
            <el-option label="Header" value="header" />
            <el-option label="Body" value="body" />
            <el-option label="Query参数" value="query" />
          </el-select>
        </el-form-item>

        <el-form-item label="签名字段名" prop="signature_field">
          <el-input v-model="formData.signature_field" placeholder="例如: Signature-Data" />
        </el-form-item>

        <el-form-item label="额外签名参数">
          <el-input
            v-model="extraParamsStr"
            type="textarea"
            :rows="4"
            placeholder='例如: {"timestamp": "${get_timestamp()}", "nonce": "${get_uuid()}"}'
          />
          <div class="form-tip">
            支持参数化函数: ${get_id()}, ${get_uuid()}, ${get_timestamp()} 等
          </div>
        </el-form-item>

        <el-form-item label="">
          <el-checkbox v-model="formData.extra_params_in_sign">额外参数参与签名</el-checkbox>
          <div class="form-tip">
            默认只对请求体进行签名。勾选后，额外参数（如 timestamp、sp_no）将参与签名计算
          </div>
        </el-form-item>

        <el-form-item label="配置描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入描述"
          />
        </el-form-item>

        <el-form-item label="状态">
          <el-checkbox v-model="formData.is_enabled">启用此配置</el-checkbox>
          <el-checkbox v-model="formData.is_default">设为项目默认配置</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 测试签名对话框 -->
    <el-dialog v-model="testDialogVisible" title="测试签名生成" width="600px">
      <el-form label-width="100px">
        <el-form-item label="请求体 (JSON)">
          <el-input
            v-model="testBodyStr"
            type="textarea"
            :rows="6"
            placeholder='例如: {"merchantId": "12345", "amount": 100.00}'
          />
        </el-form-item>

        <el-form-item label="测试结果">
          <el-input
            v-model="testResult"
            type="textarea"
            :rows="4"
            readonly
            placeholder="点击测试按钮生成签名"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="executeTest">生成签名</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Loading } from '@element-plus/icons-vue'
import * as signatureApi from '@/api/signature'
import { getApiProjects } from '@/api/api-testing'

const signatureConfigs = ref([])
const projects = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const dialogTitle = computed(() => {
  return formData.id ? '编辑签名配置' : '新建签名配置'
})
const formRef = ref(null)
const testConfig = ref(null)
const testBodyStr = ref('')
const testResult = ref('')

const formData = reactive({
  id: null,
  name: '',
  project: null,
  algorithm: 'MD5',
  secret_key: '',
  rsa_private_key: '',
  rsa_public_key: '',
  rsa_encrypt_public_key: '',
  sm2_private_key: '',
  sm2_public_key: '',
  sm2_mode: 'C1C2C3',
  signature_location: 'header',
  signature_field: 'Signature-Data',
  extra_params: {},
  extra_params_in_sign: false,
  description: '',
  is_enabled: true,
  is_default: false
})

const extraParamsStr = computed({
  get: () => formData.extra_params ? JSON.stringify(formData.extra_params, null, 2) : '',
  set: (val) => {
    try {
      formData.extra_params = val ? JSON.parse(val) : {}
    } catch (e) {
      ElMessage.error('JSON格式错误: ' + e.message)
    }
  }
})

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  algorithm: [{ required: true, message: '请选择签名算法', trigger: 'change' }],
  signature_location: [{ required: true, message: '请选择签名位置', trigger: 'change' }],
  signature_field: [{ required: true, message: '请输入签名字段名', trigger: 'blur' }]
}

// 加载签名配置列表
const loadSignatureConfigs = async () => {
  loading.value = true
  try {
    console.log('开始加载签名配置...')
    const res = await signatureApi.getSignatureConfigs()
    console.log('签名配置响应完整数据:', res)
    console.log('签名配置响应.data:', res.data)
    signatureConfigs.value = res.data.results || res.data || []
    console.log('签名配置数据:', signatureConfigs.value)
    console.log('签名配置数量:', signatureConfigs.value.length)
  } catch (error) {
    console.error('加载签名配置失败:', error)
    console.error('错误详情:', error.response?.data)
    ElMessage.error('加载签名配置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    console.log('开始加载项目列表...')
    const res = await getApiProjects()
    console.log('项目列表响应:', res)
    projects.value = res.data.results || res.data || []
    console.log('项目数量:', projects.value.length)
  } catch (error) {
    console.error('加载项目列表失败:', error)
    console.error('错误详情:', error.response?.data)
    ElMessage.error('加载项目列表失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 显示创建对话框
const showCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

// 编辑配置
const editConfig = (row) => {
  Object.assign(formData, row)
  dialogVisible.value = true
}

// 重置表单
const resetForm = () => {
  Object.assign(formData, {
    id: null,
    name: '',
    project: null,
    algorithm: 'MD5',
    secret_key: '',
    rsa_private_key: '',
    rsa_public_key: '',
    rsa_encrypt_public_key: '',
    sm2_private_key: '',
    sm2_public_key: '',
    sm2_mode: 'C1C2C3',
    signature_location: 'header',
    signature_field: 'Signature-Data',
    extra_params: {},
    extra_params_in_sign: false,
    description: '',
    is_enabled: true,
    is_default: false
  })
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

// 算法改变时清空相关密钥
const handleAlgorithmChange = (algorithm) => {
  // 清空所有密钥字段
  formData.secret_key = ''
  formData.rsa_private_key = ''
  formData.rsa_public_key = ''
  formData.rsa_encrypt_public_key = ''
  formData.sm2_private_key = ''
  formData.sm2_public_key = ''
  formData.sm2_mode = 'C1C2C3'
}

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (formData.id) {
        await signatureApi.updateSignatureConfig(formData.id, formData)
        ElMessage.success('更新成功')
      } else {
        await signatureApi.createSignatureConfig(formData)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadSignatureConfigs()
    } catch (error) {
      ElMessage.error('操作失败: ' + error.message)
    }
  })
}

// 设置为默认配置
const setDefault = async (row) => {
  try {
    await signatureApi.setDefaultSignatureConfig(row.id)
    ElMessage.success('已设置为默认配置')
    loadSignatureConfigs()
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message)
  }
}

// 删除配置
const deleteConfig = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此签名配置吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await signatureApi.deleteSignatureConfig(row.id)
    ElMessage.success('删除成功')
    loadSignatureConfigs()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

// 测试签名
const testSignature = (row) => {
  testConfig.value = row
  testBodyStr.value = ''
  testResult.value = ''
  testDialogVisible.value = true
}

// 执行测试
const executeTest = async () => {
  try {
    let testBody = {}
    if (testBodyStr.value) {
      testBody = JSON.parse(testBodyStr.value)
    }

    const res = await signatureApi.testSignature(testConfig.value.id, {
      test_body: testBody,
      test_params: testConfig.value.extra_params
    })

    testResult.value = JSON.stringify(res.data, null, 2)
    ElMessage.success('签名生成成功')
  } catch (error) {
    ElMessage.error('签名生成失败: ' + error.message)
  }
}

onMounted(() => {
  loadSignatureConfigs()
  loadProjects()
})
</script>

<style scoped>
.signature-management {
  padding: 20px;
  min-height: 400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.signature-management :deep(.el-table) {
  width: 100%;
}

.signature-management :deep(.el-table__empty-block) {
  min-height: 100px;
}
</style>
