<template>
  <div class="script-management">
    <!-- 头部工具栏 -->
    <div class="header-actions">
      <el-button type="primary" icon="el-icon-plus" @click="showCreateDialog">
        新增脚本
      </el-button>
      <el-button icon="el-icon-refresh" @click="loadScripts">
        刷新
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索脚本名称或描述"
        prefix-icon="el-icon-search"
        clearable
        @clear="loadScripts"
        @keyup.enter.native="loadScripts"
        style="width: 300px"
      />
      <el-select
        v-model="filters.project"
        placeholder="选择项目"
        clearable
        @change="loadScripts"
        style="width: 200px; margin-left: 10px"
      >
        <el-option
          v-for="project in projects"
          :key="project.id"
          :label="project.name"
          :value="project.id"
        />
      </el-select>
      <el-select
        v-model="filters.script_type"
        placeholder="脚本类型"
        clearable
        @change="loadScripts"
        style="width: 150px; margin-left: 10px"
      >
        <el-option label="Python" value="python" />
        <el-option label="JavaScript" value="javascript" />
      </el-select>
      <el-select
        v-model="filters.is_active"
        placeholder="状态"
        clearable
        @change="loadScripts"
        style="width: 120px; margin-left: 10px"
      >
        <el-option label="已激活" :value="true" />
        <el-option label="未激活" :value="false" />
      </el-select>
    </div>

    <!-- 脚本列表 -->
    <el-table
      v-loading="loading"
      :data="scripts"
      stripe
      style="width: 100%"
    >
      <el-table-column prop="name" label="脚本名称" min-width="200" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column prop="script_type_display" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.script_type === 'python' ? 'success' : 'warning'" size="small">
            {{ row.script_type === 'python' ? 'Python' : 'JavaScript' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="project_name" label="所属项目" width="200" />
      <el-table-column prop="owner.username" label="创建者" width="120" />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" @change="toggleActive(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button
            type="text"
            size="small"
            icon="el-icon-view"
            @click="viewScript(row)"
          >
            查看
          </el-button>
          <el-button
            type="text"
            size="small"
            icon="el-icon-edit"
            @click="editScript(row)"
          >
            编辑
          </el-button>
          <el-button
            type="text"
            size="small"
            icon="el-icon-delete"
            style="color: #f56c6c"
            @click="deleteScript(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.current"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadScripts"
        @size-change="loadScripts"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增脚本' : '编辑脚本'"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="scriptForm"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="脚本名称" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入脚本名称"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="脚本类型" prop="script_type">
          <el-radio-group v-model="formData.script_type">
            <el-radio label="python">Python</el-radio>
            <el-radio label="javascript">JavaScript</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属项目" prop="project">
          <el-select
            v-model="formData.project"
            placeholder="请选择项目"
            style="width: 100%"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="脚本描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入脚本描述"
          />
        </el-form-item>
        <el-form-item label="脚本内容" prop="content">
          <div class="code-editor">
            <el-select
              v-model="formData.script_type"
              placeholder="选择语言"
              style="width: 150px; margin-bottom: 10px"
              :disabled="dialogMode === 'edit'"
            >
              <el-option label="Python" value="python" />
              <el-option label="JavaScript" value="javascript" />
            </el-select>
            <el-input
              v-model="formData.content"
              type="textarea"
              :rows="15"
              :placeholder="getPlaceholder()"
            />
          </div>
          <div class="help-text">
            <p><strong>前置脚本可用变量：</strong></p>
            <ul>
              <li>request - 请求对象 {url, method, headers, params, body}</li>
              <li>environment - 环境变量对象</li>
              <li>variables - 可操作的变量对象</li>
            </ul>
            <p><strong>后置脚本可用变量：</strong></p>
            <ul>
              <li>request - 请求对象 {url, method, headers, params, body}</li>
              <li>response - 响应对象 {status_code, headers, body, json}</li>
              <li>environment - 环境变量对象</li>
              <li>variables - 可操作的变量对象</li>
            </ul>
          </div>
        </el-form-item>
        <el-form-item label="是否激活">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看脚本对话框 -->
    <el-dialog
      v-model="viewDialogVisible"
      title="脚本详情"
      width="900px"
    >
      <div v-if="currentScript">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="脚本名称">
            {{ currentScript.name }}
          </el-descriptions-item>
          <el-descriptions-item label="脚本类型">
            <el-tag :type="currentScript.script_type === 'python' ? 'success' : 'warning'">
              {{ currentScript.script_type === 'python' ? 'Python' : 'JavaScript' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="所属项目">
            {{ currentScript.project_name }}
          </el-descriptions-item>
          <el-descriptions-item label="创建者">
            {{ currentScript.owner?.username }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentScript.is_active ? 'success' : 'info'">
              {{ currentScript.is_active ? '已激活' : '未激活' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDate(currentScript.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="更新时间">
            {{ formatDate(currentScript.updated_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="脚本描述" :span="2">
            {{ currentScript.description || '无' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="script-content-view">
          <h3>脚本内容</h3>
          <pre><code>{{ currentScript.content }}</code></pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

// 响应式数据
const loading = ref(false)
const scripts = ref([])
const projects = ref([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const dialogMode = ref('create')
const submitting = ref(false)
const currentScript = ref(null)
const scriptForm = ref(null)

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const searchKeyword = ref('')
const filters = reactive({
  project: null,
  script_type: null,
  is_active: null
})

const formData = reactive({
  id: null,
  name: '',
  script_type: 'python',
  project: null,
  description: '',
  content: '',
  is_active: true
})

const formRules = {
  name: [
    { required: true, message: '请输入脚本名称', trigger: 'blur' }
  ],
  script_type: [
    { required: true, message: '请选择脚本类型', trigger: 'change' }
  ],
  project: [
    { required: true, message: '请选择项目', trigger: 'change' }
  ],
  content: [
    { required: true, message: '请输入脚本内容', trigger: 'blur' }
  ]
}

// 方法
const loadScripts = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.current,
      page_size: pagination.pageSize
    }
    
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    if (filters.project) {
      params.project = filters.project
    }
    if (filters.script_type) {
      params.script_type = filters.script_type
    }
    if (filters.is_active !== null) {
      params.is_active = filters.is_active
    }
    
    const response = await axios.get('/api/scripts/', { params })
    scripts.value = response.data.results || response.data
    pagination.total = response.data.count || 0
  } catch (error) {
    ElMessage.error('加载脚本列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const response = await axios.get('/api/projects/')
    projects.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('加载项目列表失败: ' + error.message)
  }
}

const showCreateDialog = () => {
  dialogMode.value = 'create'
  Object.assign(formData, {
    id: null,
    name: '',
    script_type: 'python',
    project: filters.project || (projects.value[0]?.id),
    description: '',
    content: '',
    is_active: true
  })
  dialogVisible.value = true
}

const editScript = (row) => {
  dialogMode.value = 'edit'
  Object.assign(formData, {
    id: row.id,
    name: row.name,
    script_type: row.script_type,
    project: row.project,
    description: row.description,
    content: row.content,
    is_active: row.is_active
  })
  dialogVisible.value = true
}

const viewScript = (row) => {
  currentScript.value = row
  viewDialogVisible.value = true
}

const submitForm = async () => {
  if (!scriptForm.value) return

  try {
    await scriptForm.value.validate()
  } catch (error) {
    return // 表单验证失败，不继续提交
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await axios.post('/api/scripts/', formData)
      ElMessage.success('脚本创建成功')
    } else {
      await axios.put(`/api/scripts/${formData.id}/`, formData)
      ElMessage.success('脚本更新成功')
    }

    dialogVisible.value = false
    loadScripts()
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message)
  } finally {
    submitting.value = false
  }
}

const deleteScript = (row) => {
  ElMessageBox.confirm(
    `确定要删除脚本"${row.name}"吗？`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await axios.delete(`/api/scripts/${row.id}/`)
      ElMessage.success('删除成功')
      loadScripts()
    } catch (error) {
      ElMessage.error('删除失败: ' + error.message)
    }
  }).catch(() => {})
}

const toggleActive = async (row) => {
  try {
    await axios.patch(`/api/scripts/${row.id}/`, { is_active: row.is_active })
    ElMessage.success('状态更新成功')
  } catch (error) {
    row.is_active = !row.is_active
    ElMessage.error('状态更新失败: ' + error.message)
  }
}

const getPlaceholder = () => {
  if (formData.script_type === 'python') {
    return `# Python 脚本示例
# 可用变量: request, environment, variables
# 修改请求头
request['headers']['X-Custom-Header'] = 'custom-value'
# 添加变量
variables['new_var'] = 'value'`
  } else {
    return `// JavaScript 脚本示例
// 可用变量: request, environment, variables
// 修改请求头
request.headers['X-Custom-Header'] = 'custom-value';
// 添加变量
variables.new_var = 'value';`
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  loadProjects()
  loadScripts()
})
</script>

<style scoped>
.script-management {
  padding: 20px;
}

.header-actions {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}

.search-bar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  text-align: center;
}

.code-editor {
  margin-bottom: 10px;
}

.help-text {
  margin-top: 10px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
}

.help-text p {
  margin: 5px 0;
  font-weight: 600;
}

.help-text ul {
  margin: 5px 0 0 20px;
}

.help-text li {
  margin: 3px 0;
}

.script-content-view {
  margin-top: 20px;
}

.script-content-view h3 {
  font-size: 16px;
  margin-bottom: 10px;
}

.script-content-view pre {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 500px;
}

.script-content-view code {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
}
</style>
