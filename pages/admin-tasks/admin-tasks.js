Page({

  data: {
    adminInfo: {},
    // 0：我的待办，1：我的已办
    currentTab: 0,
    
    // 待办任务
    tasks: [],
    // 已办任务
    completedTasks: [],
    
    // 加载状态
    loading: true,
    loadingCompleted: true
  },

  onLoad() {
    const adminInfo = wx.getStorageSync("adminInfo");
    if (!adminInfo || !adminInfo.id) {
      wx.showToast({ title: "请先登录", icon: "none" });
      setTimeout(() => {
        wx.redirectTo({ url: "/pages/admin-login/admin-login" });
      }, 1000);
      return;
    }
    this.setData({ adminInfo });
    this.loadTasks();
    this.loadCompletedTasks();
  },

  // 每次页面显示时（包括从详情页返回）都强制刷新数据
  onShow() {
    if (this.data.adminInfo.id) {
      // 每次回到页面都重新拉取数据，角标会同步更新
      this.loadTasks();
      this.loadCompletedTasks();
    }
  },

  // 切换 Tab
  switchTab(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ currentTab: Number(index) });
  },

  // 加载待办任务
  loadTasks() {
    const adminId = this.data.adminInfo.id;
    this.setData({ loading: true });
    wx.request({
      url: `http://127.0.0.1:8000/api/admin/${adminId}/pending-tasks`,
      method: "GET",
      success: (res) => {
        if (res.data.success) {
          const tasks = res.data.tasks.map(item => ({
            ...item,
            comment: '',
            approval_record_id: item.approval_record_id || item.task_id
          }));
          // 更新待办列表，角标数字（tasks.length）会自动变化
          this.setData({ tasks });
        } else {
          wx.showToast({ title: res.data.message || "获取待办失败", icon: "none" });
        }
      },
      fail: () => {
        wx.showToast({ title: "无法连接后端服务器", icon: "none" });
      },
      complete: () => this.setData({ loading: false })
    });
  },

  // 加载已办任务
  loadCompletedTasks() {
    const adminId = this.data.adminInfo.id;
    this.setData({ loadingCompleted: true });
    wx.request({
      url: `http://127.0.0.1:8000/api/admin/${adminId}/completed-tasks`,
      method: "GET",
      success: (res) => {
        if (res.data.success) {
          const tasks = res.data.tasks.map(item => ({
            ...item,
            approval_record_id: item.approval_record_id || item.task_id
          }));
          // 更新已办列表，角标数字（completedTasks.length）会自动变化
          this.setData({ completedTasks: tasks });
        } else {
          wx.showToast({ title: res.data.message || "获取已办失败", icon: "none" });
        }
      },
      fail: () => {
        wx.showToast({ title: "无法连接后端服务器", icon: "none" });
      },
      complete: () => this.setData({ loadingCompleted: false })
    });
  },

  // 下拉刷新（可选，增加用户体验）
  onPullDownRefresh() {
    if (this.data.adminInfo.id) {
      this.loadTasks();
      this.loadCompletedTasks();
      setTimeout(() => wx.stopPullDownRefresh(), 500);
    }
  },

  // 输入审批意见
  inputComment(e) {
    const taskId = e.currentTarget.dataset.taskid;
    const value = e.detail.value;
    const tasks = this.data.tasks.map(item => {
      if (item.task_id === taskId) {
        return { ...item, comment: value };
      }
      return item;
    });
    this.setData({ tasks });
  },

  // 查看详情（待办和已办共用）
  viewDetail(e) {
    const recordId = e.currentTarget.dataset.recordid;
    if (!recordId) {
      wx.showToast({ title: "缺少审批记录ID", icon: "none" });
      return;
    }
    wx.navigateTo({
      url: `/pages/admin-detail/admin-detail?recordId=${recordId}`
    });
  },

  // 点击通过
  approveTask(e) {
    const taskId = e.currentTarget.dataset.taskid;
    const task = this.data.tasks.find(item => item.task_id === taskId);
    const comment = task ? (task.comment || '') : '';
    wx.showModal({
      title: "确认审批",
      content: "确认通过该人员的审批吗？",
      success: (res) => {
        if (res.confirm) {
          this.submitApproval(taskId, "approved", comment);
        }
      }
    });
  },

  // 点击拒绝
  rejectTask(e) {
    const taskId = e.currentTarget.dataset.taskid;
    const task = this.data.tasks.find(item => item.task_id === taskId);
    const comment = task ? (task.comment || '') : '';
    if (!comment.trim()) {
      wx.showToast({ title: "请先填写拒绝原因", icon: "none" });
      return;
    }
    wx.showModal({
      title: "确认拒绝",
      content: "确认拒绝该人员的审批吗？拒绝后审批流程将结束。",
      success: (res) => {
        if (res.confirm) {
          this.submitApproval(taskId, "rejected", comment);
        }
      }
    });
  },

  // 提交审批操作
  submitApproval(taskId, action, comment) {
    const adminId = this.data.adminInfo.id;
    wx.showLoading({ title: "正在提交" });
    wx.request({
      url: `http://127.0.0.1:8000/api/approval-task/${taskId}/action`,
      method: "POST",
      header: { "content-type": "application/json" },
      data: {
        admin_id: adminId,
        action: action,
        comment: comment
      },
      success: (res) => {
        if (res.data.success) {
          wx.showToast({
            title: action === "approved" ? "审批通过" : "已拒绝审批",
            icon: "success"
          });
          // 审批完成后，立即刷新待办和已办，角标会变化
          setTimeout(() => {
            this.loadTasks();
            this.loadCompletedTasks();
          }, 1000);
        } else {
          wx.showToast({ title: res.data.message || "审批失败", icon: "none" });
        }
      },
      fail: () => {
        wx.showToast({ title: "无法连接服务器", icon: "none" });
      },
      complete: () => wx.hideLoading()
    });
  }

});