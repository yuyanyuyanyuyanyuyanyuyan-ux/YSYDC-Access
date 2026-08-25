Page({

  data: {

    name: "",
    phone: "",
    company: "",
    identityType: "",
    purpose: "",

    identityTypes: [
      "客户",
      "设备厂商",
      "施工人员",
      "访客",
      "其他"
    ]

  },


  /* 输入姓名 */

  inputName(e) {

    this.setData({
      name: e.detail.value
    })

  },


  /* 输入手机号 */

  inputPhone(e) {

    this.setData({
      phone: e.detail.value
    })

  },


  /* 输入公司 */

  inputCompany(e) {

    this.setData({
      company: e.detail.value
    })

  },


  /* 选择身份 */

  identityChange(e) {

    const index = e.detail.value

    this.setData({
      identityType: this.data.identityTypes[index]
    })

  },


  /* 输入访问目的 */

  inputPurpose(e) {

    this.setData({
      purpose: e.detail.value
    })

  },


  /* 提交表单 */

  submitForm() {

    const {
      name,
      phone,
      company,
      identityType,
      purpose
    } = this.data


    /* =========================
       姓名校验
    ========================= */

    if (!name.trim()) {

      wx.showToast({
        title: "请输入姓名",
        icon: "none"
      })

      return

    }


    /* =========================
       手机号校验
    ========================= */

    if (!phone) {

      wx.showToast({
        title: "请输入手机号",
        icon: "none"
      })

      return

    }


    /* 手机号格式校验 */

    const phoneReg = /^1[3-9]\d{9}$/

    if (!phoneReg.test(phone)) {

      wx.showToast({
        title: "请输入正确的手机号",
        icon: "none"
      })

      return

    }


    /* =========================
       公司校验
    ========================= */

    if (!company.trim()) {

      wx.showToast({
        title: "请输入公司或单位",
        icon: "none"
      })

      return

    }


    /* =========================
       身份类型校验
    ========================= */

    if (!identityType) {

      wx.showToast({
        title: "请选择身份类型",
        icon: "none"
      })

      return

    }


    /* =========================
       访问目的校验
    ========================= */

    if (!purpose.trim()) {

      wx.showToast({
        title: "请输入访问目的",
        icon: "none"
      })

      return

    }


    /* =========================
       表单校验通过
    ========================= */

    wx.showModal({

      title: "信息确认",

      content: "信息填写完成，确认后将提交登记信息。",

      success: (res) => {

        if (!res.confirm) {

          return

        }


        /* 显示加载状态 */

        wx.showLoading({
          title: "正在提交"
        })


        /* =========================
           向 FastAPI 提交数据
        ========================= */

        wx.request({

          url: 'http://127.0.0.1:8000/api/register',

          method: 'POST',

          header: {
            'content-type': 'application/json'
          },


          data: {

            name: name,

            phone: phone,

            company: company,

            identity_type: identityType,

            visit_purpose: purpose

          },


          success: (response) => {

            console.log("后端返回结果：", response.data)


            /* 判断后端是否登记成功 */

            if (response.data.success) {


              /* 保存后端返回的用户 ID */

              wx.setStorageSync(
                'user_id',
                response.data.user_id
              )


              console.log(
                "当前用户 ID：",
                response.data.user_id
              )


              wx.showToast({

                title: "登记成功",

                icon: "success",

                duration: 1500

              })


              /* 延迟后跳转安全须知 */

              setTimeout(() => {

                wx.navigateTo({
                  url: '/pages/safety/safety'
                })

              }, 1500)


            } else {

              wx.showToast({

                title: "登记失败",

                icon: "none"

              })

            }

          },


          fail: (error) => {

            console.error(
              "请求后端失败：",
              error
            )


            wx.showToast({

              title: "无法连接服务器",

              icon: "none"

            })

          },


          complete: () => {

            wx.hideLoading()

          }

        })

      }

    })

  }

})