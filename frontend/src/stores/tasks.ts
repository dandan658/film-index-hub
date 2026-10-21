// 任务管理状态
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiService } from '@/services'
import type { Task, CreateTaskRequest, UpdateTaskRequest } from '@/types'
import { TASK_STATUS } from '@/utils/constants'
import { getErrorMessage } from '@/utils/helpers'

export const useTaskStore = defineStore('tasks', () => {
  // 状态
  const tasks = ref<Task[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedTaskIds = ref<Set<number>>(new Set())

  // 计算属性
  const tasksByStatus = computed(() => {
    const groups = {
      normal: [] as Task[],
      error: [] as Task[],
      running: [] as Task[],
      success: [] as Task[]
    }
    
    tasks.value.forEach(task => {
      const status = task.status as keyof typeof groups
      if (groups[status]) {
        groups[status].push(task)
      }
    })
    
    return groups
  })

  const taskCategories = computed(() => {
    const categories = new Set<string>()
    tasks.value.forEach(task => {
      if (task.category) {
        categories.add(task.category)
      }
    })
    return Array.from(categories)
  })

  const taskSavePaths = computed(() => {
    const paths = new Set<string>()
    tasks.value.forEach(task => {
      if (task.save_dir) {
        paths.add(task.save_dir)
      }
    })
    return Array.from(paths)
  })

  const taskCronRules = computed(() => {
    const crons = new Set<string>()
    tasks.value.forEach(task => {
      if (task.cron) {
        crons.add(task.cron)
      }
    })
    return Array.from(crons)
  })

  const taskRegexPatterns = computed(() => {
    const patterns = new Set<string>()
    tasks.value.forEach(task => {
      if (task.regex_pattern) {
        patterns.add(task.regex_pattern)
      }
    })
    return Array.from(patterns)
  })

  const taskRegexReplaces = computed(() => {
    const replaces = new Set<string>()
    tasks.value.forEach(task => {
      if (task.regex_replace) {
        replaces.add(task.regex_replace)
      }
    })
    return Array.from(replaces)
  })

  // 获取最新任务的保存路径的父目录作为默认路径
  const getDefaultSavePath = computed(() => {
    if (tasks.value.length === 0) return ''
    
    // 找到order最大的任务（最新任务）
    const latestTask = tasks.value.reduce((latest, current) => {
      return (current.order > latest.order) ? current : latest
    })
    
    if (!latestTask.save_dir) return ''
    
    // 获取路径的父目录
    const pathParts = latestTask.save_dir.split('/').filter(part => part.length > 0)
    pathParts.pop() // 移除最后一部分（文件/文件夹名）
    const basePath = pathParts.join('/')
    return basePath ? `/${basePath}` : ''
  })

  const taskStats = computed(() => {
    const stats = {
      total: tasks.value.length,
      normal: 0,
      error: 0,
      running: 0,
      success: 0
    }

    tasks.value.forEach(task => {
      const status = task.status as keyof typeof stats
      if (stats.hasOwnProperty(status)) {
        stats[status]++
      }
    })

    return stats
  })

  const selectedTasks = computed(() => {
    return tasks.value.filter(task => selectedTaskIds.value.has(task.order))
  })

  // 操作方法
  const fetchTasks = async () => {
    loading.value = true
    error.value = null
    
    try {
      const response = await apiService.getTasks()
      if (response.success) {
        const taskList = response.tasks || response.data?.tasks || []
        tasks.value = taskList.sort((a: Task, b: Task) => (a.order || 0) - (b.order || 0))
      } else {
        throw new Error(response.message || '获取任务列表失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      console.error('获取任务列表失败:', err)
    } finally {
      loading.value = false
    }
  }

  const addTask = async (taskData: CreateTaskRequest) => {
    try {
      const response = await apiService.createTask(taskData)
      if (response.success) {
        await fetchTasks() // 重新获取任务列表
        return true
      } else {
        throw new Error(response.message || '添加任务失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const updateTask = async (taskId: number, taskData: UpdateTaskRequest) => {
    try {
      const response = await apiService.updateTask(taskId, taskData)
      if (response.success) {
        await fetchTasks() // 重新获取任务列表
        return true
      } else {
        throw new Error(response.message || '更新任务失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const deleteTask = async (taskId: number) => {
    try {
      const response = await apiService.deleteTask(taskId)
      if (response.success) {
        await fetchTasks() // 重新获取任务列表
        selectedTaskIds.value.delete(taskId)
        return true
      } else {
        throw new Error(response.message || '删除任务失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const executeTask = async (taskId: number) => {
    const task = tasks.value.find(t => t.order - 1 === taskId)
    if (!task) throw new Error('任务不存在，请刷新后重试')
    try {
      // Keep the selected object even if polling reorders the list.
      if (task) {
        task.status = TASK_STATUS.RUNNING
        task.message = '正在执行...'
      }

      const response = await apiService.executeTask(taskId, task?.task_uid)
      if (!response.success) {
        throw new Error(response.message || '执行任务失败')
      }

      // A response may never replace another row's stable identity.
      if (task?.task_uid && response.task_uid && task.task_uid !== response.task_uid) {
        throw new Error('任务标识不匹配，请刷新后重试')
      }

      return response
    } catch (err) {
      // Restore only the selected identity after a failed request.
      if (task) {
        task.status = TASK_STATUS.ERROR
        task.message = getErrorMessage(err)
      }
      
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const executeBatchTasks = async (taskIds: number[], taskUids?: string[]) => {
    const selected = taskUids?.length
      ? taskUids.map(uid => tasks.value.find(task => task.task_uid === uid))
      : taskIds.map(id => tasks.value.find(task => task.order - 1 === id))
    if (selected.some(task => !task)) throw new Error('任务已变化，请刷新后重新选择')
    const targets = selected as Task[]
    try {
      targets.forEach(task => { task.status = TASK_STATUS.RUNNING; task.message = '正在执行...' })
      const uids = targets.map(task => task.task_uid)
      const response = await apiService.executeBatchTasks(taskIds, uids.every((uid): uid is string => !!uid) ? uids : undefined)
      if (!response.success) throw new Error(response.message || '批量执行任务失败')
      return response.results || response.data?.results
    } catch (err) {
      targets.forEach(task => { task.status = TASK_STATUS.ERROR; task.message = getErrorMessage(err) })
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const deleteBatchTasks = async (taskIds: number[]) => {
    try {
      const response = await apiService.deleteBatchTasks(taskIds)
      if (response.success) {
        await fetchTasks() // 重新获取任务列表
        // 清除选中状态
        taskIds.forEach(id => selectedTaskIds.value.delete(id))
        return true
      } else {
        throw new Error(response.message || '批量删除任务失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const shareTask = async (taskId: number, options?: { password?: string, period?: number }) => {
    try {
      const response = await apiService.shareTask(taskId, options)
      if (response.success) {
        // 更新任务的分享信息
        const task = tasks.value.find(t => t.order === taskId)
        if (task) {
          task.share_info = response.share_info || response.data?.share_info
        }
        return response.share_info || response.data?.share_info
      } else {
        throw new Error(response.message || '生成分享链接失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  const moveTask = async (taskId: number, newIndex: number) => {
    try {
      const response = await apiService.moveTask(taskId, newIndex)
      if (response.success) {
        await fetchTasks() // 重新获取任务列表
        return true
      } else {
        throw new Error(response.message || '移动任务失败')
      }
    } catch (err) {
      error.value = getErrorMessage(err)
      throw err
    }
  }

  // 轮询更新处理
  const handleTaskUpdate = (updatedTasks: Task[]) => {
    // 更新任务列表
    const previous = new Map(tasks.value.map(task => [task.task_uid || task.order, task]))
    const next = [...updatedTasks].sort((a, b) => (a.order || 0) - (b.order || 0)).map(incoming => {
      const existing = previous.get(incoming.task_uid || incoming.order)
      if (!existing) return incoming
      for (const key of Object.keys(existing)) {
        if (!(key in incoming)) delete (existing as any)[key]
      }
      for (const [key, value] of Object.entries(incoming)) {
        const oldValue = (existing as any)[key]
        if (oldValue !== value && (typeof value !== 'object' || JSON.stringify(oldValue) !== JSON.stringify(value))) {
          (existing as any)[key] = value
        }
      }
      return existing
    })
    if (next.length !== tasks.value.length || next.some((task, index) => task !== tasks.value[index])) {
      tasks.value = next
    }
  }

  // 选择操作
  const selectTask = (taskId: number) => {
    selectedTaskIds.value.add(taskId)
  }

  const unselectTask = (taskId: number) => {
    selectedTaskIds.value.delete(taskId)
  }

  const selectAllTasks = () => {
    tasks.value.forEach(task => {
      selectedTaskIds.value.add(task.order)
    })
  }

  const clearSelection = () => {
    selectedTaskIds.value.clear()
  }

  const toggleTaskSelection = (taskId: number) => {
    if (selectedTaskIds.value.has(taskId)) {
      selectedTaskIds.value.delete(taskId)
    } else {
      selectedTaskIds.value.add(taskId)
    }
  }

  const clearError = () => {
    error.value = null
  }

  return {
    // 状态
    tasks,
    loading,
    error,
    selectedTaskIds,
    
    // 计算属性
    tasksByStatus,
    taskCategories,
    taskSavePaths,
    taskCronRules,
    taskRegexPatterns,
    taskRegexReplaces,
    getDefaultSavePath,
    taskStats,
    selectedTasks,
    
    // 操作方法
    fetchTasks,
    addTask,
    updateTask,
    deleteTask,
    executeTask,
    executeBatchTasks,
    deleteBatchTasks,
    shareTask,
    moveTask,
    handleTaskUpdate,
    
    // 选择操作
    selectTask,
    unselectTask,
    selectAllTasks,
    clearSelection,
    toggleTaskSelection,

    clearError
  }
})
