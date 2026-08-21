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


    /* 姓名校验 */

    if (!name.trim()) {

      wx.showToast({
        title: "请输入姓名",
        icon: "none"
      })

      return

    }


    /* 手机号校验 */

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


    /* 公司校验 */

    if (!company.trim()) {

      wx.showToast({
        title: "请输入公司或单位",
        icon: "none"
      })

      return

    }


    /* 身份类型校验 */

    if (!identityType) {

      wx.showToast({
        title: "请选择身份类型",
        icon: "none"
      })

      return

    }


    /* 访问目的校验 */

    if (!purpose.trim()) {

      wx.showToast({
        title: "请输入访问目的",
        icon: "none"
      })

      return

    }


    /*
      当前阶段：
      表单校验成功

      后面接入后端后，
      就在这里使用 wx.request()
      将数据发送到 FastAPI
    */


    console.log("表单校验成功")

    console.log({
      name,
      phone,
      company,
      identityType,
      purpose
    })


    wx.showModal({

      title: "信息确认",

      content:
        "信息填写完成，点击确认后进入下一步。",

      success(res) {

        if (res.confirm) {

          /*
            下一阶段跳转到
            安全须知页面
          */

            wx.navigateTo({
              url: '/pages/safety/safety'
            })

        }

      }

    })

  }

})