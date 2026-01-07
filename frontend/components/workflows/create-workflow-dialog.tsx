'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from '@/components/ui/use-toast'
import * as workflowsApi from '@/lib/api/workflows'

interface CreateWorkflowDialogProps {
  children?: React.ReactNode
}

/**
 * 创建 Workflow 的 Dialog 组件
 */
export function CreateWorkflowDialog({ children }: CreateWorkflowDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  // 表单状态
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('trading')

  // 创建 mutation
  const createMutation = useMutation({
    mutationFn: (data: workflowsApi.CreateWorkflowRequest) => 
      workflowsApi.createWorkflow(data),
    onSuccess: (data) => {
      toast({
        title: 'Workflow Created',
        description: `Successfully created workflow "${data.display_name || data.name}"`,
      })
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      resetForm()
      setOpen(false)
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to create workflow',
        variant: 'destructive',
      })
    },
  })

  // 重置表单
  const resetForm = () => {
    setName('')
    setDisplayName('')
    setDescription('')
    setCategory('trading')
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Workflow name is required',
        variant: 'destructive',
      })
      return
    }

    createMutation.mutate({
      name: name.trim(),
      display_name: displayName.trim() || undefined,
      description: description.trim() || undefined,
      category,
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Workflow
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Workflow</DialogTitle>
            <DialogDescription>
              Create a new workflow to define your trading strategy pipeline.
              You can add nodes and edges after creation.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 名称（必填） */}
            <div className="grid gap-2">
              <Label htmlFor="name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder="e.g. aggressive_momentum_strategy"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                Unique identifier, use lowercase with underscores
              </p>
            </div>

            {/* 显示名称（可选） */}
            <div className="grid gap-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                placeholder="e.g. Aggressive Momentum Strategy"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>

            {/* 分类 */}
            <div className="grid gap-2">
              <Label htmlFor="category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="trading">Trading</SelectItem>
                  <SelectItem value="analysis">Analysis</SelectItem>
                  <SelectItem value="risk">Risk Management</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* 描述（可选） */}
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Describe what this workflow does..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                resetForm()
                setOpen(false)
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Workflow
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

